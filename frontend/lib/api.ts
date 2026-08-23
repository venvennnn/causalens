import type {
  GraphPayload,
  NextPayload,
  PipelineEvent,
  PipelineSource,
  RipplePayload,
  WhyPayload,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.message || body.detail?.message || message;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  analyze: (query: string) =>
    request<GraphPayload>("/analyze", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
  analysis: (id: string) => request<GraphPayload>(`/analysis/${id}`),
  why: (eventId: string, analysisId: string) =>
    request<WhyPayload>(`/events/${eventId}/why?analysis_id=${encodeURIComponent(analysisId)}`),
  next: (eventId: string, analysisId: string) =>
    request<NextPayload>(`/events/${eventId}/next?analysis_id=${encodeURIComponent(analysisId)}`),
  ripple: (eventId: string, analysisId: string) =>
    request<RipplePayload>(`/events/${eventId}/ripple?analysis_id=${encodeURIComponent(analysisId)}`),
  pipelineStatus: () =>
    request<{ sources: PipelineSource[]; gdelt: { health: string; display_name: string } }>(
      "/pipeline/status",
    ),
  pipelineEvents: () => request<{ events: PipelineEvent[] }>("/pipeline/events"),
  healingEvent: (source: string, collectorId: string, message: string) =>
    request("/pipeline/healing-event", {
      method: "POST",
      body: JSON.stringify({ source, collector_id: collectorId, message }),
    }),
  refresh: () => request("/ingest/refresh", { method: "POST" }),
};
