import { GoogleGenAI } from '@google/genai';
import type { IncomingMessage, ServerResponse } from 'http';

export interface GroundingSource {
  title: string;
  url: string;
}

export interface ChatRequestPayload {
  messages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }>;
  model?: string;
  searchGrounding?: boolean;
  systemInstruction?: string;
  stream?: boolean;
}

const DEFAULT_SYSTEM_INSTRUCTION = `You are Strike Tips Racing AI, an elite South African horse racing intelligence analyst.
Your mission:
1. Evaluate runners based on form, course history, going conditions, draw bias, and jockey/trainer strike rates.
2. Identify genuine value betting opportunities where your estimated probability exceeds the implied market price (Edge > 5%).
3. Enforce disciplined bankroll governance with Half-Kelly criteria (never risking more than 5% of bankroll).
4. For exotics (Pick 6, Jackpot, Trifecta), prioritize high-value bankers and smart permutation spreads.
5. Provide concise, bold, professional verdicts with clear bottom-line recommendations.`;

/**
 * Intelligent auto-router: analyzes query intent and context to pick the optimal model.
 */
function resolveAutoModel(lastMessage: string, hasKey: { gemini: boolean; groq: boolean }): { target: string; isGroq: boolean } {
  const q = lastMessage.toLowerCase();

  // 1. Complex deep reasoning, multi-leg exotics, mathematical Kelly optimization -> Gemini Pro
  if (
    q.includes('pick 6') || q.includes('jackpot') || q.includes('trifecta') ||
    q.includes('kelly') || q.includes('calculate edge') || q.includes('mathematical') ||
    q.includes('monte carlo') || q.includes('permutation') || q.includes('compare runners')
  ) {
    if (hasKey.gemini) return { target: 'gemini-3.1-pro-preview', isGroq: false };
    if (hasKey.groq) return { target: 'openai/gpt-oss-120b', isGroq: true };
  }

  // 2. High-speed quick lookups, balance checks, short questions -> Groq Llama 8B or Gemini Lite
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

  // 3. Fast racing speed / versatile analysis -> Groq Llama 70B if available
  if (q.includes('fast') || q.includes('quick summary')) {
    if (hasKey.groq) return { target: 'openai/gpt-oss-120b', isGroq: true };
  }

  // Default champion: Gemini 3.5 Flash with Google Search Grounding for live race info
  if (hasKey.gemini) {
    return { target: 'gemini-3.5-flash', isGroq: false };
  }
  if (hasKey.groq) {
    return { target: 'openai/gpt-oss-120b', isGroq: true };
  }
  return { target: 'gemini-3.5-flash', isGroq: false };
}

export async function handleChatRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
  if (req.method !== 'POST') {
    res.writeHead(405, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Method Not Allowed' }));
    return;
  }

  let bodyStr = '';
  req.on('data', chunk => {
    bodyStr += chunk;
  });

  req.on('end', async () => {
    try {
      const body: ChatRequestPayload = JSON.parse(bodyStr || '{}');
      const messages = body.messages || [];
      if (!messages.length) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Messages list cannot be empty' }));
        return;
      }

      const rawModel = (body.model || 'auto').toLowerCase();
      const searchGrounding = body.searchGrounding !== false;
      const isStream = body.stream !== false;
      const systemInstruction = body.systemInstruction || DEFAULT_SYSTEM_INSTRUCTION;

      const hasGeminiKey = Boolean(process.env.GEMINI_API_KEY);
      const hasGroqKey = Boolean(process.env.GROQ_API_KEY);

      let chosenModel = rawModel;
      let isGroq = false;

      // Auto routing resolution
      if (rawModel === 'auto' || rawModel === 'strike-tips') {
        const lastUserMsg = [...messages].reverse().find(m => m.role === 'user')?.content || '';
        const routed = resolveAutoModel(lastUserMsg, { gemini: hasGeminiKey, groq: hasGroqKey });
        chosenModel = routed.target;
        isGroq = routed.isGroq;
      } else if (rawModel.includes('groq') || rawModel.includes('llama') || rawModel.includes('mixtral') || rawModel.includes('gemma-2')) {
        isGroq = true;
      }

      if (isGroq) {
        await handleGroqChat(res, body, chosenModel, systemInstruction, isStream);
        return;
      }

      // Gemini models
      await handleGeminiChat(res, body, chosenModel, systemInstruction, searchGrounding, isStream);
    } catch (err: any) {
      console.error('[Chat Service Error]', err);
      if (!res.headersSent) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message || 'Chat generation failed' }));
      }
    }
  });
}

async function handleGeminiChat(
  res: ServerResponse,
  body: ChatRequestPayload,
  modelName: string,
  systemInstruction: string,
  searchGrounding: boolean,
  isStream: boolean
): Promise<void> {
  const geminiApiKey = process.env.GEMINI_API_KEY;
  if (!geminiApiKey) {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'GEMINI_API_KEY is not configured on the server.' }));
    return;
  }

  // Model resolution
  let targetModel = 'gemini-3.5-flash';
  if (modelName.includes('pro') || modelName.includes('complex')) {
    targetModel = 'gemini-3.1-pro-preview';
  } else if (modelName.includes('lite') || modelName.includes('fast')) {
    targetModel = 'gemini-3.1-flash-lite';
  } else if (modelName.includes('3.8-flash')) {
    targetModel = 'gemini-2.5-flash';
  }

  const ai = new GoogleGenAI({ apiKey: geminiApiKey });

  // Map messages to Gemini format
  const formattedContents = body.messages
    .filter(m => m.role !== 'system')
    .map(m => ({
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: m.content }],
    }));

  // Configure tools (Google Search Grounding for gemini-3.5-flash)
  const config: any = {
    systemInstruction,
  };

  if (targetModel === 'gemini-3.5-flash' && searchGrounding) {
    config.tools = [{ googleSearch: {} }];
  }

  if (isStream) {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
    });

    try {
      const stream = await ai.models.generateContentStream({
        model: targetModel,
        contents: formattedContents,
        config,
      });

      let finalGroundingSources: GroundingSource[] = [];

      for await (const chunk of stream) {
        const text = chunk.text || '';
        if (text) {
          const sseChunk = {
            choices: [{ delta: { content: text } }],
          };
          res.write(`data: ${JSON.stringify(sseChunk)}\n\n`);
        }

        // Check for grounding metadata
        const metadata = chunk.candidates?.[0]?.groundingMetadata;
        if (metadata?.groundingChunks) {
          const sources: GroundingSource[] = [];
          for (const c of metadata.groundingChunks) {
            if (c.web?.uri && c.web?.title) {
              sources.push({ title: c.web.title, url: c.web.uri });
            }
          }
          if (sources.length > 0) {
            finalGroundingSources = sources;
          }
        }
      }

      // Send final stop payload with grounding sources
      const endPayload = {
        choices: [{ delta: { content: '' }, finish_reason: 'stop' }],
        model: targetModel,
        groundingSources: finalGroundingSources,
      };
      res.write(`data: ${JSON.stringify(endPayload)}\n\n`);
      res.write('data: [DONE]\n\n');
      res.end();
    } catch (streamErr: any) {
      console.error('[Gemini Stream Error]', streamErr);
      res.write(`data: ${JSON.stringify({ error: streamErr.message })}\n\n`);
      res.write('data: [DONE]\n\n');
      res.end();
    }
  } else {
    // Non-streaming fallback
    const response = await ai.models.generateContent({
      model: targetModel,
      contents: formattedContents,
      config,
    });

    const candidate = response.candidates?.[0];
    const text = response.text || '';
    const sources: GroundingSource[] = [];

    const metadata = candidate?.groundingMetadata;
    if (metadata?.groundingChunks) {
      for (const c of metadata.groundingChunks) {
        if (c.web?.uri && c.web?.title) {
          sources.push({ title: c.web.title, url: c.web.uri });
        }
      }
    }

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      content: text,
      model: targetModel,
      groundingSources: sources,
    }));
  }
}

async function handleGroqChat(
  res: ServerResponse,
  body: ChatRequestPayload,
  modelName: string,
  systemInstruction: string,
  isStream: boolean
): Promise<void> {
  const groqApiKey = process.env.GROQ_API_KEY;
  if (!groqApiKey) {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'GROQ_API_KEY is not configured on the server.' }));
    return;
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
  } else if (modelName.includes('llama3-70b-8192')) {
    groqModel = 'llama3-70b-8192';
  }

  const groqMessages = [
    { role: 'system', content: systemInstruction },
    ...body.messages.map(m => ({
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: m.content,
    })),
  ];

  const groqRes = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${groqApiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: groqModel,
      messages: groqMessages,
      stream: isStream,
      temperature: 0.6,
      max_tokens: 1500,
    }),
  });

  if (!groqRes.ok) {
    const errText = await groqRes.text();
    res.writeHead(groqRes.status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: `Groq error: ${errText}` }));
    return;
  }

  if (isStream && groqRes.body) {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
    });

    const reader = groqRes.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunkStr = decoder.decode(value, { stream: true });
      res.write(chunkStr);
    }
    const endChunk = {
      choices: [{ delta: { content: '' }, finish_reason: 'stop' }],
      model: groqModel,
    };
    res.write(`data: ${JSON.stringify(endChunk)}\n\n`);
    res.write('data: [DONE]\n\n');
    res.end();
  } else {
    const data = await groqRes.json();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
  }
}
