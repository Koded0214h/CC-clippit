import { API_URL } from "./client";
import { getAccessToken } from "./tokenStorage";

/** Topics the ops socket can stream. Each snapshot has the same shape as its REST twin. */
export type OpsTopic = "system" | "webhooks" | "social" | "notifications";

export type OpsMessage =
  | { type: "ready"; topics: OpsTopic[]; snapshot_seconds: number }
  | { type: "snapshot"; topic: OpsTopic; data: unknown }
  | { type: "event"; topic: "webhooks"; event: { ts: number; path: string; status: number; duration_ms: number; provider: "payments" | "social"; title: string; result: "complete" | "rejected" | "failed" } }
  | { type: "subscribed"; topics: OpsTopic[] }
  | { type: "error"; topic: OpsTopic; message: string }
  | { type: "pong" };

export type OpsSocketState = "connecting" | "live" | "reconnecting" | "unauthorized";

/**
 * Connects to /admin/ws, authenticates with the operator's access token (sent as the first
 * message — never in the URL), and reconnects with backoff. Close code 4401/4403 means the
 * token was rejected: it stops retrying and reports "unauthorized" so the caller can fall back
 * to REST polling or send the operator to sign in.
 */
export function openOpsSocket(opts: {
  topics?: OpsTopic[];
  onMessage: (message: OpsMessage) => void;
  onState?: (state: OpsSocketState) => void;
}): () => void {
  const url = `${API_URL.replace(/^http/, "ws")}/admin/ws`;
  let socket: WebSocket | null = null;
  let closed = false;
  let attempt = 0;
  let pingTimer: ReturnType<typeof setInterval> | undefined;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;

  const connect = () => {
    opts.onState?.(attempt === 0 ? "connecting" : "reconnecting");
    const token = getAccessToken();
    if (!token) { opts.onState?.("unauthorized"); return; }
    socket = new WebSocket(url);
    socket.onopen = () => {
      socket?.send(JSON.stringify({ type: "auth", token }));
      if (opts.topics) socket?.send(JSON.stringify({ type: "subscribe", topics: opts.topics }));
      pingTimer = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send(JSON.stringify({ type: "ping" })), 25000);
    };
    socket.onmessage = (event) => {
      let message: OpsMessage;
      try { message = JSON.parse(event.data as string) as OpsMessage; } catch { return; }
      if (message.type === "ready") { attempt = 0; opts.onState?.("live"); }
      opts.onMessage(message);
    };
    socket.onclose = (event) => {
      clearInterval(pingTimer);
      if (closed) return;
      if (event.code === 4401 || event.code === 4403) { opts.onState?.("unauthorized"); return; }
      attempt += 1;
      opts.onState?.("reconnecting");
      retryTimer = setTimeout(connect, Math.min(15000, 1000 * 2 ** Math.min(attempt, 4)));
    };
  };
  connect();

  return () => { closed = true; clearInterval(pingTimer); clearTimeout(retryTimer); socket?.close(); };
}
