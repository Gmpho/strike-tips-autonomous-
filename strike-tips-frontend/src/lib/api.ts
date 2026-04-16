// API utility to connect to FastAPI backend
// Backend runs on port 8000, routes already include /api prefix
const API_BASE_URL = 'http://127.0.0.1:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

// Increased timeout to 180 seconds to allow for CPU model warm-up
const fetchWithTimeout = async (url: string, options: RequestInit = {}, timeout = 180000): Promise<Response> => {
  const timeoutController = new AbortController();
  const id = setTimeout(() => timeoutController.abort(), timeout);
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers as Record<string, string>,
  };
  
  if (API_KEY) {
    headers['X-API-KEY'] = API_KEY;
  }

  // Combine external signal with timeout signal
  const signals = [timeoutController.signal];
  if (options.signal) signals.push(options.signal);
  
  // Use AbortSignal.any if available (Node 20+ / Modern browsers)
  // Fallback for older environments:
  if (options.signal) {
    options.signal.addEventListener('abort', () => timeoutController.abort());
  }

  try {
    const response = await fetch(url, { ...options, headers, signal: timeoutController.signal });
    clearTimeout(id);
    return response;
  } catch (err: any) {
    if (err.name === 'AbortError') {
      if (options.signal?.aborted) {
        console.warn('Fetch aborted by user (Kill Switch)');
        throw new Error('Operation cancelled by user.');
      }
      console.error('Fetch aborted: Request timed out');
      throw new Error('Request timed out - the local model is taking too long to load.');
    }
    throw err;
  }
};

export interface Race {
  track: string;
  race_number: number;
  race_time: string;
  distance: string;
  runners: Runner[];
}

export interface Runner {
  name: string;
  number?: number;
  odds: number;
  weight?: number;
  draw?: number;
  jockey?: string;
  trainer?: string;
  form?: string;
}

export interface ValueBet {
  horse: string;
  odds: number;
  edge: number;
  confidence: string;
  reason: string;
  stake: number;
}

export interface Bet {
  track: string;
  race_number: number;
  horse: string;
  odds: number;
  edge_percent: number;
  confidence: string;
  stake?: number;
}

export interface BankrollStatus {
  current_bankroll: number;
  peak_bankroll: number;
  total_profit_loss: number;
  drawdown_percent: number;
  performance: {
    total_bets: number;
    win_rate: number;
    roi: number;
    profit_loss: number;
    avg_stake: number;
  };
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  thought?: string; // For "Thought Trace"
}

// API Functions
export async function getStatus(): Promise<BankrollStatus> {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/status`);
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
}

export async function sendMessage(message: string, model?: string, signal?: AbortSignal): Promise<ChatMessage> {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, model }),
    signal
  });
  if (!res.ok) throw new Error('Failed to send message to agent');
  const data = await res.json();
  
  return {
    role: 'assistant',
    content: data.response,
    timestamp: data.timestamp || new Date().toISOString()
  };
}

export async function getChatHistory(): Promise<ChatMessage[]> {
  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/agent/history`);
    if (!res.ok) throw new Error('Failed to fetch chat history');
    const data = await res.json();
    if (data.success && data.history) {
      return data.history.map((msg: any) => ({
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp || new Date().toISOString()
      }));
    }
    return [];
  } catch (err) {
    console.error('getChatHistory error:', err);
    return [];
  }
}

export async function clearChatHistory(): Promise<boolean> {
  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/agent/history/clear`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to clear chat history');
    const data = await res.json();
    return data.success;
  } catch (err) {
    console.error('clearChatHistory error:', err);
    return false;
  }
}

export async function getTracks() {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/tracks`);
  if (!res.ok) throw new Error('Failed to fetch tracks');
  return res.json();
}

export async function getMonitoringSnapshot() {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/monitoring/snapshot`);
  if (!res.ok) throw new Error('Failed to fetch monitoring snapshot');
  return res.json();
}

export async function getPerformanceSummary() {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/monitoring/performance`);
  if (!res.ok) throw new Error('Failed to fetch performance summary');
  return res.json();
}

export async function runScan(tracks?: string[]) {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tracks),
  });
  if (!res.ok) throw new Error('Failed to run scan');
  return res.json();
}

export async function searchRacing(query: string) {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/search/${encodeURIComponent(query)}`);
  if (!res.ok) throw new Error('Failed to search');
  return res.json();
}

export async function addManualRace(race: Race) {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/races/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(race),
  });
  if (!res.ok) throw new Error('Failed to add race');
  return res.json();
}

export async function getRaceTemplate() {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/races/template`);
  if (!res.ok) throw new Error('Failed to get template');
  return res.json();
}

export async function placeBet(bet: Bet) {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/bets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bet),
  });
  if (!res.ok) throw new Error('Failed to place bet');
  return res.json();
}

export async function getBets() {
  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/bets`);
    if (!res.ok) return { bets: [] };
    return res.json();
  } catch {
    return { bets: [] };
  }
}

export async function getOpenBets() {
  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/bets/open`);
    if (!res.ok) return { bets: [] };
    return res.json();
  } catch {
    return { bets: [] };
  }
}

export async function settleBet(betId: string, won: boolean, notes?: string) {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/bets/settle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bet_id: betId, won, notes }),
  });
  if (!res.ok) throw new Error('Failed to settle bet');
  return res.json();
}

export async function getConfig() {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/config`);
  if (!res.ok) throw new Error('Failed to fetch config');
  return res.json();
}

export interface ModelInfo {
  id: string;
  name: string;
  type: string;
  provider: string;
  description: string;
  
  // Capabilities
  supports_tools: boolean;
  is_orchestrator: boolean;
  is_reasoning: boolean;
  is_fast: boolean;
  is_free: boolean;
  rate_limit_risk: string;
  
  // Status
  is_available: boolean;
  status_reason: string;
}

export async function getModels(): Promise<{models: ModelInfo[], count: number}> {
  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/api/models`);
    if (!res.ok) throw new Error('Failed to fetch models');
    return res.json();
  } catch {
    return { models: [], count: 0 };
  }
}

export async function analyzeRace(track: string, raceNumber: number) {
  const res = await fetchWithTimeout(`${API_BASE_URL}/api/racing/analyze/${encodeURIComponent(track)}/${raceNumber}`);
  if (!res.ok) throw new Error('Failed to analyze race');
  return res.json();
}
