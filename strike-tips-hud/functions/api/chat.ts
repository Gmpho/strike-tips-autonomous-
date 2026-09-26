// Pages Function: POST /api/chat — AI racing chat (Gemini/Groq auto-router).
// Production port of server/chat-service.ts (dev-only vite plugin).
// LLM spend protection: per-IP rate limit + capped max_tokens + body cap.
// Auth: keyless like other reads (browser carries no key); abuse contained
// by IP rate limiting. Secrets come from Pages env (server-side only).

import { hitRate as boundedHitRate, type RateEntry } from '../lib/rate-limit.ts';

interface Env {
  GEMINI_API_KEY?: string;
  GROQ_API_KEY?: string;
}

interface GroundingSource {
  title: string;
  url: string;
}

const RATE_WINDOW_MS = 60_000;
const RATE_MAX = 20; // LLM calls/min per IP
const GLOBAL_RATE_MAX = 150; // isolate-wide ceiling: 20/IP no longer scales to many IPs
// Exported for the ai-spend-guard pin tests (values must not silently drift).
export const MAX_BODY_BYTES = 32_768; // per-call input cap (pinned; see ai-spend-guard spec)
export const MAX_TOKENS = 1500; // per-call output cap (pinned; see ai-spend-guard spec)
// Bounded stores (shared limiter): evict-on-rollover + hard key cap.
const rateStore = new Map<string, RateEntry>();
const globalStore = new Map<string, RateEntry>();

function hitRate(ip: string): boolean {
  return boundedHitRate(rateStore, ip, RATE_MAX, RATE_WINDOW_MS);
}

function hitGlobalRate(): boolean {
  return boundedHitRate(globalStore, '__global__', GLOBAL_RATE_MAX, RATE_WINDOW_MS);
}

function corsHeaders(origin: string): Record<string, string> {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-API-KEY, Authorization',
    'Access-Control-Max-Age': '86400',
  };
}

const DEFAULT_SYSTEM_INSTRUCTION = `You are Strike Tips Racing AI, an elite South African horse racing intelligence analyst.
Your mission:
1. Evaluate runners based on form, course history, going conditions, draw bias, and jockey/trainer strike rates.
2. Identify genuine value betting opportunities where your estimated probability exceeds the implied market price (Edge > 5%).
3. Enforce disciplined bankroll governance with Half-Kelly criteria (never risking more than 5% of bankroll).
4. For exotics (Pick 6, Jackpot, Trifecta), prioritize high-value bankers and smart permutation spreads.
5. Provide concise, bold, professional verdicts with clear bottom-line recommendations.`;

function resolveAutoModel(lastMessage: string, hasKey: { gemini: boolean; groq: boolean }): { target: string; isGroq: boolean } {
  const q = lastMessage.toLowerCase();
  if (
    q.includes('pick 6') || q.includes('jackpot') || q.includes('trifecta') ||
    q.includes('kelly') || q.includes('calculate edge') || q.includes('mathematical') ||
    q.includes('monte carlo') || q.includes('permutation') || q.includes('compare runners')
  ) {
    if (hasKey.gemini) return { target: 'gemini-3.1-pro-preview', isGroq: false };
    if (hasKey.groq) return { target: 'openai/gpt-oss-120b', isGroq: true };
  }
  if (
    q.length < 50 && (
      q.includes('balance') || q.includes('time') || q.includes('hello') ||
      q.includes('rules') || q.includes('what is') || q.includes('help') ||
      q.includes('status') || q.includes('ping')
    )
  ) {
    if (hasKey.groq) return { target: 'openai/gpt-oss-20b', isGroq: true };
    if (hasKey.gemini) return { target: 'gemini-3.1-flash-lite', isGroq: false };
  }
  if (q.includes('fast') || q.includes('quick summary')) {
    if (hasKey.groq) return { target: 'openai/gpt-oss-120b', isGroq: true };
  }
  if (hasKey.gemini) {
    return { target: 'gemini-3.5-flash', isGroq: false };
  }
  if (hasKey.groq) {
    return { target: 'openai/gpt-oss-120b', isGroq: true };
  }
  return { target: 'gemini-3.5-flash', isGroq: false };
}

export const onRequest: PagesFunction<Env> = async (context) => {
  const { request, env } = context;
  const url = new URL(request.url);
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders(url.origin) });
  }
  if (request.method !== 'POST') {
    return Response.json({ error: 'Method Not Allowed' }, { status: 405, headers: corsHeaders(url.origin) });
  }
  const ip = request.headers.get('cf-connecting-ip') || 'unknown';
  if (hitRate(ip) || hitGlobalRate()) {
    return Response.json({ error: 'Too Many Requests' }, { status: 429, headers: { ...corsHeaders(url.origin), 'Retry-After': '60' } });
  }

  let body: any;
  try {
    const text = await request.text();
    if (text.length > MAX_BODY_BYTES) {
      return Response.json({ error: 'Request too large' }, { status: 413, headers: corsHeaders(url.origin) });
    }
    body = JSON.parse(text || '{}');
  } catch {
    return Response.json({ error: 'Invalid JSON' }, { status: 400, headers: corsHeaders(url.origin) });
  }
  const messages = body.messages || [];
  if (!messages.length) {
    return Response.json({ error: 'Messages list cannot be empty' }, { status: 400, headers: corsHeaders(url.origin) });
  }

  const rawModel = String(body.model || 'auto').toLowerCase();
  const searchGrounding = body.searchGrounding !== false;
  const isStream = body.stream !== false;
  const systemInstruction = body.systemInstruction || DEFAULT_SYSTEM_INSTRUCTION;
  const hasGeminiKey = Boolean(env.GEMINI_API_KEY);
  const hasGroqKey = Boolean(env.GROQ_API_KEY);

  let chosenModel = rawModel;
  let isGroq = false;
  if (rawModel === 'auto' || rawModel === 'strike-tips') {
    const lastUserMsg = [...messages].reverse().find((m: any) => m.role === 'user')?.content || '';
    const routed = resolveAutoModel(lastUserMsg, { gemini: hasGeminiKey, groq: hasGroqKey });
    chosenModel = routed.target;
    isGroq = routed.isGroq;
  } else if (rawModel.includes('groq') || rawModel.includes('llama') || rawModel.includes('mixtral') || rawModel.includes('gemma-2')) {
    isGroq = true;
  }

  try {
    if (isGroq) return await handleGroqChat(env, body, chosenModel, systemInstruction, isStream, url.origin);
    return await handleGeminiChat(env, body, chosenModel, systemInstruction, searchGrounding, isStream, url.origin);
  } catch (err: any) {
    return Response.json({ error: err.message || 'Chat generation failed' }, { status: 500, headers: corsHeaders(url.origin) });
  }
};

async function handleGeminiChat(env: Env, body: any, modelName: string, systemInstruction: string, searchGrounding: boolean, isStream: boolean, origin: string): Promise<Response> {
  const geminiApiKey = env.GEMINI_API_KEY;
  if (!geminiApiKey) {
    return Response.json({ error: 'GEMINI_API_KEY is not configured on the server.' }, { status: 400, headers: corsHeaders(origin) });
  }
  let targetModel = 'gemini-3.5-flash';
  if (modelName.includes('pro') || modelName.includes('complex')) {
    targetModel = 'gemini-3.1-pro-preview';
  } else if (modelName.includes('lite') || modelName.includes('fast')) {
    targetModel = 'gemini-3.1-flash-lite';
  } else if (modelName.includes('3.8-flash')) {
    targetModel = 'gemini-2.5-flash';
  }

  const formattedContents = body.messages
    .filter((m: any) => m.role !== 'system')
    .map((m: any) => ({
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: String(m.content || '').slice(0, 8000) }],
    }));
  const config: any = { systemInstruction, maxOutputTokens: MAX_TOKENS };
  if (targetModel === 'gemini-3.5-flash' && searchGrounding) {
    config.tools = [{ googleSearch: {} }];
  }

  if (!isStream) {
    const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${targetModel}:generateContent?key=${geminiApiKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contents: formattedContents, generationConfig: { maxOutputTokens: MAX_TOKENS, temperature: 0.6 }, tools: config.tools, systemInstruction: { parts: [{ text: systemInstruction }] } }),
    });
    if (!resp.ok) {
      return Response.json({ error: `Gemini error: ${await resp.text()}` }, { status: resp.status, headers: corsHeaders(origin) });
    }
    const data: any = await resp.json();
    const candidate = data.candidates?.[0];
    const sources: GroundingSource[] = [];
    for (const c of candidate?.groundingMetadata?.groundingChunks || []) {
      if (c.web?.uri && c.web?.title) sources.push({ title: c.web.title, url: c.web.uri });
    }
    return Response.json({ content: data.candidates?.[0]?.content?.parts?.map((p: any) => p.text || '').join('') || '', model: targetModel, groundingSources: sources }, { headers: corsHeaders(origin) });
  }

  // SSE streaming via REST streamGenerateContent:alternate (server-sent events)
  const upstream = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${targetModel}:streamGenerateContent?alt=sse&key=${geminiApiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ contents: formattedContents, generationConfig: { maxOutputTokens: MAX_TOKENS, temperature: 0.6 }, tools: config.tools, systemInstruction: { parts: [{ text: systemInstruction }] } }),
  });
  if (!upstream.ok || !upstream.body) {
    return Response.json({ error: `Gemini error: ${await upstream.text()}` }, { status: upstream.status, headers: corsHeaders(origin) });
  }
  const reader = upstream.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalSources: GroundingSource[] = [];
  const out = new ReadableStream({
    async pull(controller) {
      const { done, value } = await reader.read();
      if (done) {
        controller.enqueue(new TextEncoder().encode(
          `data: ${JSON.stringify({ choices: [{ delta: { content: '' }, finish_reason: 'stop' }], model: targetModel, groundingSources: finalSources })}\n\ndata: [DONE]\n\n`,
        ));
        controller.close();
        return;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        const t = line.trim();
        if (!t.startsWith('data:')) continue;
        const payload = t.slice(5).trim();
        if (!payload || payload === '[DONE]') continue;
        try {
          const evt = JSON.parse(payload);
          const text = evt.candidates?.[0]?.content?.parts?.map((p: any) => p.text || '').join('') || '';
          const gm = evt.candidates?.[0]?.groundingMetadata;
          if (gm?.groundingChunks) {
            const srcs: GroundingSource[] = [];
            for (const c of gm.groundingChunks) {
              if (c.web?.uri && c.web?.title) srcs.push({ title: c.web.title, url: c.web.uri });
            }
            if (srcs.length) finalSources = srcs;
          }
          if (text) {
            controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({ choices: [{ delta: { content: text } }] })}\n\n`));
          }
        } catch { /* partial chunk — wait for more */ }
      }
    },
  });
  return new Response(out, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache, no-transform', 'Connection': 'keep-alive', ...corsHeaders(origin) } });
}

async function handleGroqChat(env: Env, body: any, modelName: string, systemInstruction: string, isStream: boolean, origin: string): Promise<Response> {
  const groqApiKey = env.GROQ_API_KEY;
  if (!groqApiKey) {
    return Response.json({ error: 'GROQ_API_KEY is not configured on the server.' }, { status: 400, headers: corsHeaders(origin) });
  }
  let groqModel = 'openai/gpt-oss-120b';
  if (modelName.includes('8b') || modelName.includes('20b') || modelName.includes('instant')) {
    groqModel = 'openai/gpt-oss-20b';
  } else if (modelName.includes('70b') || modelName.includes('120b') || modelName.includes('llama-3.3')) {
    groqModel = 'openai/gpt-oss-120b';
  } else if (modelName.includes('mixtral') || modelName.includes('8x7b')) {
    groqModel = 'openai/gpt-oss-20b';
  } else if (modelName.includes('gemma-2-9b') || modelName.includes('gemma2')) {
    groqModel = 'openai/gpt-oss-20b';
  }
  const groqMessages = [
    { role: 'system', content: systemInstruction },
    ...body.messages.map((m: any) => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: String(m.content || '').slice(0, 8000) })),
  ];
  const groqRes = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: { Authorization: `Bearer ${groqApiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: groqModel, messages: groqMessages, stream: isStream, temperature: 0.6, max_tokens: MAX_TOKENS }),
  });
  if (!groqRes.ok) {
    return Response.json({ error: `Groq error: ${await groqRes.text()}` }, { status: groqRes.status, headers: corsHeaders(origin) });
  }
  if (isStream && groqRes.body) {
    const reader = groqRes.body.getReader();
    const out = new ReadableStream({
      async pull(controller) {
        const { done, value } = await reader.read();
        if (done) {
          controller.enqueue(new TextEncoder().encode(
            `data: ${JSON.stringify({ choices: [{ delta: { content: '' }, finish_reason: 'stop' }], model: groqModel })}\n\ndata: [DONE]\n\n`,
          ));
          controller.close();
          return;
        }
        controller.enqueue(value);
      },
    });
    return new Response(out, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache, no-transform', 'Connection': 'keep-alive', ...corsHeaders(origin) } });
  }
  return Response.json(await groqRes.json(), { headers: corsHeaders(origin) });
}
