// Shared upstream-AI error mapping (Pages Functions + vite dev server).
// Dependency-free so both runtimes can import it. Raw provider JSON
// ("RESOURCE_EXHAUSTED ... GenerateContentInputTokensPerModelPerDay-FreeTier")
// must NEVER reach users — map to plain words + a support link.

export const GEMINI_LIMITS_URL = 'https://ai.dev/rate-limit';
export const GROQ_MODELS_URL = 'https://console.groq.com/docs/models';

export interface FriendlyError {
  error: string;
  code: 'QUOTA_EXHAUSTED' | 'BAD_KEY' | 'MODEL_UNAVAILABLE' | 'UPSTREAM_ERROR';
  supportUrl: string;
  model: string;
}

export function friendlyUpstreamError(
  status: number,
  raw: string,
  provider: 'Gemini' | 'Groq',
  model: string,
): FriendlyError {
  const l = String(raw || '').toLowerCase();
  const supportUrl = provider === 'Gemini' ? GEMINI_LIMITS_URL : GROQ_MODELS_URL;

  const quotaHit =
    status === 429 ||
    l.includes('quota') ||
    l.includes('resource_exhausted') ||
    l.includes('retryinfo') ||
    l.includes('rate limit') ||
    l.includes('too many requests');
  if (quotaHit) {
    return {
      error: `⚠️ ${provider} free quota is used up for ${model} — wait a minute and retry, or enable billing for higher limits. Limits: ${supportUrl}`,
      code: 'QUOTA_EXHAUSTED',
      supportUrl,
      model,
    };
  }

  const badKey =
    status === 400 && (l.includes('api key') || l.includes('api_key_invalid') || l.includes('invalid api key')) ||
    status === 401 || status === 403;
  if (badKey) {
    return {
      error: `⚠️ The server's ${provider} key was rejected — an admin needs to set a valid key.`,
      code: 'BAD_KEY',
      supportUrl,
      model,
    };
  }

  const modelGone =
    status === 404 ||
    l.includes('not found') ||
    l.includes('does not exist') ||
    l.includes('decommission') ||
    l.includes('deprecat') ||
    l.includes('invalid model');
  if (modelGone) {
    return {
      error: `⚠️ ${model} isn't available on your ${provider} plan (retired, preview-ended, or Enterprise-only). Switch to Auto Router or a production model — live list: ${supportUrl}`,
      code: 'MODEL_UNAVAILABLE',
      supportUrl,
      model,
    };
  }

  return {
    error: `${provider} error: ${String(raw || 'unknown').slice(0, 300)}`,
    code: 'UPSTREAM_ERROR',
    supportUrl,
    model,
  };
}
