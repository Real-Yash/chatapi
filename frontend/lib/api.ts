// Backend client for ChatAPI.
// Base URL defaults to http://localhost:8000 (set NEXT_PUBLIC_API_URL to override).

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

const TOKEN_KEY = "chatapi_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

async function handleRes(res: Response): Promise<any> {
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const msg =
      (data && (data.detail || data.message || data.error)) ||
      `Request failed (${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

function extractToken(data: any): string | null {
  if (!data) return null;
  if (typeof data === "string") return data;
  return (
    data.access_token || data.token || data.jwt || data.accessToken || null
  );
}

// ---------- Auth ----------

export async function signup(input: {
  name: string;
  email: string;
  password: string;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const data = await handleRes(res);
  const token = extractToken(data);
  if (token) setToken(token);
  return data;
}

export async function login(input: {
  email: string;
  password: string;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const data = await handleRes(res);
  const token = extractToken(data);
  if (token) setToken(token);
  return data;
}

export async function me(): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: authHeaders(),
  });
  return handleRes(res);
}

// ---------- Agents ----------

export type Agent = {
  id: string;
  name: string;
  slug: string;
  welcome_message?: string;
  primary_color?: string;
  tone?: string;
  model?: string;
  status?: string;
  created_at?: string;
  [key: string]: any;
};

export async function listAgents(): Promise<Agent[]> {
  const res = await fetch(`${API_BASE}/agents`, { headers: authHeaders() });
  const data = await handleRes(res);
  return Array.isArray(data) ? data : data?.agents || data?.items || [];
}

export async function createAgent(input: { name: string }): Promise<Agent> {
  const res = await fetch(`${API_BASE}/agents`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(input),
  });
  return handleRes(res);
}

export async function getAgent(id: string): Promise<Agent> {
  const res = await fetch(`${API_BASE}/agents/${id}`, {
    headers: authHeaders(),
  });
  return handleRes(res);
}

export async function updateAgent(id: string, patch: any): Promise<Agent> {
  const res = await fetch(`${API_BASE}/agents/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(patch),
  });
  return handleRes(res);
}

export async function deleteAgent(id: string): Promise<any> {
  const res = await fetch(`${API_BASE}/agents/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handleRes(res);
}

// ---------- Knowledge ----------

export type KnowledgeItem = {
  id: string;
  type: "text" | "file" | "url";
  title: string;
  content?: string;
  url?: string;
  file_name?: string;
  status: "ready" | "processing" | "failed";
  created_at?: string;
  [key: string]: any;
};

export async function listKnowledge(agentId: string): Promise<KnowledgeItem[]> {
  const res = await fetch(`${API_BASE}/agents/${agentId}/knowledge`, {
    headers: authHeaders(),
  });
  const data = await handleRes(res);
  return Array.isArray(data) ? data : data?.items || data?.knowledge || [];
}

export async function addTextKnowledge(
  agentId: string,
  input: { title: string; content: string }
): Promise<any> {
  const res = await fetch(`${API_BASE}/agents/${agentId}/knowledge/text`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(input),
  });
  return handleRes(res);
}

export async function uploadFileKnowledge(
  agentId: string,
  file: File
): Promise<any> {
  const token = getToken();
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/agents/${agentId}/knowledge/file`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  });
  return handleRes(res);
}

export async function addUrlKnowledge(
  agentId: string,
  input: { url: string }
): Promise<any> {
  const res = await fetch(`${API_BASE}/agents/${agentId}/knowledge/url`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(input),
  });
  return handleRes(res);
}

export async function deleteKnowledge(
  agentId: string,
  knowledgeId: string
): Promise<any> {
  const res = await fetch(
    `${API_BASE}/agents/${agentId}/knowledge/${knowledgeId}`,
    { method: "DELETE", headers: authHeaders() }
  );
  return handleRes(res);
}

// ---------- API keys ----------

export type ApiKey = {
  id: string;
  name: string;
  key_prefix?: string;
  prefix?: string;
  created_at?: string;
  last_used_at?: string | null;
  [key: string]: any;
};

export async function listApiKeys(agentId: string): Promise<ApiKey[]> {
  const res = await fetch(`${API_BASE}/agents/${agentId}/api-keys`, {
    headers: authHeaders(),
  });
  const data = await handleRes(res);
  return Array.isArray(data) ? data : data?.keys || data?.items || [];
}

export async function createApiKey(
  agentId: string,
  input: { name: string }
): Promise<any> {
  const res = await fetch(`${API_BASE}/agents/${agentId}/api-keys`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(input),
  });
  return handleRes(res);
}

export async function deleteApiKey(
  agentId: string,
  keyId: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/agents/${agentId}/api-keys/${keyId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handleRes(res);
}

// ---------- Public agent ----------

export async function getPublicAgent(slug: string): Promise<Agent> {
  const res = await fetch(`${API_BASE}/public/agents/${slug}`);
  return handleRes(res);
}

// ---------- Streaming ----------

export type ChatMessage = { role: "user" | "assistant" | "system"; content: string };
export type Citation = { title?: string; url?: string; snippet?: string; [k: string]: any };

export type StreamHandlers = {
  onToken?: (token: string) => void;
  onCitations?: (citations: Citation[]) => void;
  signal?: AbortSignal;
};

/**
 * Stream a chat completion. Supports:
 *  - SSE: lines like `data: {"token": "..."}`, `data: {"citations": [...]}`, `data: [DONE]`
 *  - Plain-text streaming fallback (append raw chunks)
 * Returns full text + citations.
 */
export async function streamChat(
  url: string,
  body: any,
  handlers: StreamHandlers & { auth?: boolean } = {}
): Promise<{ text: string; citations: Citation[] }> {
  const { onToken, onCitations, signal, auth } = handlers;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const t = getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;
  }
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    await handleRes(res);
  }
  if (!res.body) {
    const json: any = await res.json().catch(() => null);
    const text = json?.answer || json?.message || json?.text || "";
    const citations = json?.citations || [];
    if (text && onToken) onToken(text);
    if (citations.length && onCitations) onCitations(citations);
    return { text, citations };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";
  let citations: Citation[] = [];

  const emitLine = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed === ": ping") return;
    const payload = trimmed.startsWith("data:")
      ? trimmed.slice(5).trim()
      : trimmed;
    if (payload === "[DONE]") return;
    try {
      const obj = JSON.parse(payload);
      if (typeof obj === "string") {
        full += obj;
        onToken?.(obj);
      } else if (obj.token) {
        full += obj.token;
        onToken?.(obj.token);
      } else if (obj.delta) {
        full += obj.delta;
        onToken?.(obj.delta);
      } else if (obj.text) {
        full += obj.text;
        onToken?.(obj.text);
      } else if (obj.answer && !full) {
        full += obj.answer;
        onToken?.(obj.answer);
      }
      if (obj.citations && Array.isArray(obj.citations)) {
        citations = obj.citations;
        onCitations?.(citations);
      }
    } catch {
      // Not JSON — treat as raw text delta
      if (payload && !payload.startsWith("{")) {
        full += payload;
        onToken?.(payload);
      }
    }
  };

  let done = false;
  let leftoverRaw = "";
  while (!done) {
    const { value, done: d } = await reader.read();
    done = d;
    const chunk = decoder.decode(value || new Uint8Array(), { stream: !done });
    if (!chunk && done) break;
    // If content-type is not event-stream, treat as raw text
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("text/event-stream") && !chunk.includes("data:")) {
      leftoverRaw += chunk;
      full += chunk;
      onToken?.(chunk);
      continue;
    }
    buffer += chunk;
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) emitLine(line);
  }
  if (buffer.trim()) emitLine(buffer);
  // If we accumulated raw but server actually sent one JSON blob, normalize
  if (leftoverRaw) {
    try {
      const obj = JSON.parse(leftoverRaw);
      if (obj.answer || obj.text) {
        full = obj.answer || obj.text;
      }
      if (Array.isArray(obj.citations)) citations = obj.citations;
    } catch {
      /* keep raw */
    }
  }
  return { text: full, citations };
}

export function streamPublicChat(
  slug: string,
  message: string,
  history: ChatMessage[],
  handlers: StreamHandlers = {}
) {
  return streamChat(
    `${API_BASE}/chat/${slug}`,
    { message, history },
    handlers
  );
}

export function streamPlaygroundChat(
  agentId: string,
  message: string,
  history: ChatMessage[],
  handlers: StreamHandlers = {}
) {
  return streamChat(
    `${API_BASE}/agents/${agentId}/chat`,
    { message, history },
    { ...handlers, auth: true }
  );
}
