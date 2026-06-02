import { useEffect, useRef, useState } from "react";

export type ProgressEvent = {
  task_id: string;
  state: string;
  progress_pct: number;
  progress_message?: string;
  ts: number;
};

export function useTaskProgress(taskId: string | null): ProgressEvent | null {
  const [event, setEvent] = useState<ProgressEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!taskId) {
      setEvent(null);
      return;
    }
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
        /* ignore */
      }
    };
    ws.onerror = () => {
      /* swallow; the polling query still works */
    };
    return () => ws.close();
  }, [taskId]);

  return event;
}
