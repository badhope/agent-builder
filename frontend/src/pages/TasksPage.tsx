import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { convertApi } from "@/api/convert";
import { Spinner } from "@/components/ui/Spinner";
import { useTaskProgress } from "@/hooks/useTaskProgress";
import { RefreshCw, X, Download, Eye, AlertCircle } from "lucide-react";
import type { Task } from "@/types/api";

const STATES = ["", "pending", "running", "succeeded", "failed", "cancelled"];

export default function TasksPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [state, setState] = useState<string>("");
  const [subscribed, setSubscribed] = useState<string[]>([]);
  const [actingIds, setActingIds] = useState<Set<string>>(new Set());
  const live = useTaskProgress(subscribed.length > 0 ? subscribed[0] : null);

  const tasks = useQuery({
    queryKey: ["tasks", { state }],
    queryFn: () => convertApi.listTasks({ state: state || undefined, limit: 100 }),
    refetchInterval: subscribed.length > 0 ? false : 5000,
  });

  if (tasks.isLoading) return <Spinner fullscreen />;

  if (tasks.isError) {
    return (
      <div className="card p-6 text-center">
        <AlertCircle className="mx-auto h-8 w-8 text-red-500" />
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          Failed to load tasks.
        </p>
        <button
          onClick={() => tasks.refetch()}
          className="btn-secondary mt-3"
        >
          <RefreshCw className="h-4 w-4" /> Retry
        </button>
      </div>
    );
  }

  const markActing = (id: string) => setActingIds((s) => new Set(s).add(id));
  const unmarkActing = (id: string) =>
    setActingIds((s) => {
      const n = new Set(s);
      n.delete(id);
      return n;
    });

  const retry = async (t: Task) => {
    markActing(t.id);
    try {
      await convertApi.retryTask(t.id);
      qc.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Retrying…");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      unmarkActing(t.id);
    }
  };

  const cancel = async (t: Task) => {
    markActing(t.id);
    try {
      await convertApi.cancelTask(t.id);
      qc.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Task cancelled");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      unmarkActing(t.id);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Tasks</h1>
        <select
          className="input w-40"
          value={state}
          onChange={(e) => setState(e.target.value)}
        >
          {STATES.map((s) => (
            <option key={s} value={s}>
              {s || "all"}
            </option>
          ))}
        </select>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-900">
            <tr>
              <th className="px-3 py-2">State</th>
              <th className="px-3 py-2">Source → Target</th>
              <th className="px-3 py-2">Progress</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {tasks.data?.items.map((t) => (
              <tr
                key={t.id}
                className="hover:bg-slate-50 dark:hover:bg-slate-900/40"
                onMouseEnter={() => setSubscribed((p) => (p.includes(t.id) ? p : [...p, t.id]))}
              >
                <td className="px-3 py-2">
                  <span
                    className={`badge ${
                      t.state === "succeeded"
                        ? "bg-emerald-100 text-emerald-700"
                        : t.state === "failed"
                          ? "bg-red-100 text-red-700"
                          : t.state === "running" || t.state === "queued"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {t.state}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {t.source_format} → {t.target_format}
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                      <div
                        className="h-full bg-brand-500"
                        style={{ width: `${t.progress_pct}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-500">
                      {subscribed.includes(t.id) && live ? live.progress_pct : t.progress_pct}%
                    </span>
                  </div>
                </td>
                <td className="px-3 py-2 text-xs text-slate-500">
                  {new Date(t.created_at).toLocaleString()}
                </td>
                <td className="px-3 py-2 text-right">
                  <div className="flex justify-end gap-1">
                    {t.state === "succeeded" && t.output_file_id && (
                      <a
                        href={convertApi.downloadUrl(t.output_file_id)}
                        className="btn-ghost p-1"
                        title="Download"
                      >
                        <Download className="h-4 w-4" />
                      </a>
                    )}
                    {(t.state === "failed" || t.state === "cancelled") && (
                      <button
                        onClick={() => retry(t)}
                        disabled={actingIds.has(t.id)}
                        className="btn-ghost p-1"
                        title="Retry"
                      >
                        {actingIds.has(t.id) ? (
                          <Spinner size={14} />
                        ) : (
                          <RefreshCw className="h-4 w-4" />
                        )}
                      </button>
                    )}
                    {(t.state === "pending" || t.state === "running" || t.state === "queued") && (
                      <button
                        onClick={() => cancel(t)}
                        disabled={actingIds.has(t.id)}
                        className="btn-ghost p-1"
                        title="Cancel"
                      >
                        {actingIds.has(t.id) ? (
                          <Spinner size={14} />
                        ) : (
                          <X className="h-4 w-4" />
                        )}
                      </button>
                    )}
                    <button
                      onClick={() => navigate(`/tasks/${t.id}`)}
                      className="btn-ghost p-1"
                      title="View details"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {tasks.data?.items.length === 0 && (
              <tr>
                <td colSpan={5} className="p-6 text-center text-slate-500">
                  No tasks match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
