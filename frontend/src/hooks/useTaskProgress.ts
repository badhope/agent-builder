import { useEffect, useRef, useState } from "react";

export type ProgressEvent = {
  task_id: string;
  state: string;
  progress_pct: number;
  progress_message?: string;
  ts: number;
};

/**
 * Subscribe to live progress events for a task.
 *
 * Returns the most recent event, or `null` if no task is being watched.
 *
 * NOTE: this is intentionally minimal. We don't back off, we don't
 * surface connection state to the caller, and we silently fall back
 * to whatever polling the parent component is doing. The TanStack
 * Query fallback in the page is the source of truth — this hook is
 * an "early update" optimization so the bar moves without waiting
 * for the next 3s poll.
 *
 * TODO: extract a shared `useWebSocket` that handles reconnect-with-
 * backoff and exposes a `status: 'connecting' | 'open' | 'closed'`
 * state. The chat page needs the same logic. For now, the duplicate
 * is small enough that I'm leaving it.
 */
export function useTaskProgress(taskId: string | null): ProgressEvent | null {
  const [event, setEvent] = useState<ProgressEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!taskId) {
      setEvent(null);
      return;
    }
    // auth store stores the access token under "docconv.auth" — see
    // src/stores/auth.ts. Couldn't import the store directly here
    // because of a circular dep I never got around to fixing.
    const token = localStorage.getItem("docconv.auth")
      ? JSON.parse(localStorage.getItem("docconv.auth")!).state.accessToken
      : null;
    const base = import.meta.env.VITE_WS_BASE ?? "ws://localhost:8000";
    const url = `${base}/ws/tasks/${taskId}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as ProgressEvent;
        setEvent(data);
      } catch {
        // Server sometimes sends a ping frame as a string. Ignore.
      }
    };
    ws.onerror = () => {
      // swallow; the polling query still works
    };
    return () => ws.close();
  }, [taskId]);

  return event;
}
