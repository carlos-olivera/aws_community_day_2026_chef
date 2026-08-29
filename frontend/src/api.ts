import type { EventSummary, Menu, Run, Stats, SurveySubmission } from "./types";

export const EVENT_ID = "demo-event";
const PRESENTER_SESSION_KEY = "chef-andino-presenter-key";
const RESPONSE_KEY = "chef-andino-response-key";
const volatileSession = new Map<string, string>();

function readSessionValue(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key) ?? volatileSession.get(key) ?? null;
  } catch {
    // Safari/Firefox private modes and embedded webviews can reject storage access.
    return volatileSession.get(key) ?? null;
  }
}

function writeSessionValue(key: string, value: string): void {
  volatileSession.set(key, value);
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // The in-memory value is sufficient for this tab and never persists PII.
  }
}

function removeSessionValue(key: string): void {
  volatileSession.delete(key);
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // Storage was unavailable; the volatile copy was already removed.
  }
}

function createAnonymousIdempotencyKey(): string {
  try {
    if (typeof globalThis.crypto?.randomUUID === "function") {
      return globalThis.crypto.randomUUID();
    }
  } catch {
    // Some older secure-context implementations expose randomUUID but reject its use.
  }

  try {
    const bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex
      .slice(6, 8)
      .join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
  } catch {
    // Last-resort uniqueness for restricted webviews; this is not a security token.
    return `anon-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }
}

async function request<T>(path: string, init: RequestInit = {}, protectedRoute = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (protectedRoute) {
    const passphrase = readSessionValue(PRESENTER_SESSION_KEY);
    if (passphrase) headers.set("Authorization", `Bearer ${passphrase}`);
  }
  const response = await fetch(path, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function savePresenterKey(value: string): void {
  writeSessionValue(PRESENTER_SESSION_KEY, value);
}

export function hasPresenterKey(): boolean {
  return Boolean(readSessionValue(PRESENTER_SESSION_KEY));
}

export function clearPresenterKey(): void {
  removeSessionValue(PRESENTER_SESSION_KEY);
}

export function submitResponse(submission: SurveySubmission): Promise<unknown> {
  let key = readSessionValue(RESPONSE_KEY);
  if (!key) {
    key = createAnonymousIdempotencyKey();
    writeSessionValue(RESPONSE_KEY, key);
  }
  return request(`/api/events/${EVENT_ID}/responses`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body: JSON.stringify(submission),
  });
}

export const fetchEvent = (): Promise<EventSummary> => request(`/api/events/${EVENT_ID}`);
export const fetchStats = (): Promise<Stats> => request(`/api/events/${EVENT_ID}/stats`);
export const fetchMenu = (): Promise<Menu> => request(`/api/events/${EVENT_ID}/menu`);

export function resetEvent(seedSynthetic: boolean): Promise<{ state: string; cycle: number; seeded: number }> {
  return request(
    `/api/events/${EVENT_ID}/reset`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seedSynthetic }),
    },
    true,
  );
}

export function freezeEvent(): Promise<unknown> {
  return request(`/api/events/${EVENT_ID}/freeze`, { method: "POST" }, true);
}

export function generateMenu(): Promise<{ state: string; run_id: string }> {
  return request(`/api/events/${EVENT_ID}/generate`, { method: "POST" }, true);
}

export function fetchRun(runId: string): Promise<Run> {
  return request(`/api/events/${EVENT_ID}/runs/${runId}`, {}, true);
}

export function revealFallback(): Promise<{ published: boolean; run_id: string }> {
  return request(`/api/events/${EVENT_ID}/fallback/reveal`, { method: "POST" }, true);
}
