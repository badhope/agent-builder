import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { convertApi } from "@/api/convert";
import { formatBytes } from "@/utils/format";
import { Spinner } from "@/components/ui/Spinner";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  FileText,
  XCircle,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

export default function DashboardPage() {
  const tasks = useQuery({
    queryKey: ["tasks", { state: "", limit: 100 }],
    queryFn: () => convertApi.listTasks({ limit: 100 }),
  });
  const files = useQuery({
    queryKey: ["files", { limit: 5 }],
    queryFn: () => convertApi.listFiles(),
  });

  if (tasks.isLoading || files.isLoading) return <Spinner fullscreen />;

  if (tasks.isError || files.isError) {
    return (
      <div className="card p-6 text-center">
        <AlertCircle className="mx-auto h-8 w-8 text-red-500" />
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          Failed to load dashboard data.
        </p>
        <button
          onClick={() => { tasks.refetch(); files.refetch(); }}
          className="btn-secondary mt-3"
        >
          <RefreshCw className="h-4 w-4" /> Retry
        </button>
      </div>
    );
  }

  const items = tasks.data?.items ?? [];
  const stats = {
    total: tasks.data?.total ?? 0,
    succeeded: items.filter((t) => t.state === "succeeded").length,
    failed: items.filter((t) => t.state === "failed").length,
    running: items.filter((t) => t.state === "running" || t.state === "queued").length,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <Link to="/convert" className="btn-primary">
          New conversion <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        {[
          { label: "Total tasks", value: stats.total, icon: FileText, color: "text-brand-600" },
          { label: "Succeeded", value: stats.succeeded, icon: CheckCircle2, color: "text-emerald-600" },
          { label: "Running", value: stats.running, icon: Clock, color: "text-amber-600" },
          { label: "Failed", value: stats.failed, icon: XCircle, color: "text-red-600" },
        ].map((s) => (
          <div key={s.label} className="card p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs uppercase text-slate-500">{s.label}</div>
                <div className="text-2xl font-semibold">{s.value}</div>
              </div>
              <s.icon className={`h-6 w-6 ${s.color}`} />
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card">
          <header className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-800">
            <h2 className="font-medium">Recent tasks</h2>
            <Link to="/tasks" className="text-sm text-brand-600 hover:underline">
              See all
            </Link>
          </header>
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {tasks.data?.items.map((t) => (
              <li key={t.id} className="flex items-center gap-3 p-3 text-sm">
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
                <div className="min-w-0 flex-1 truncate">
                  {t.source_format.toUpperCase()} → {t.target_format.toUpperCase()}
                </div>
                <div className="text-xs text-slate-500">
                  {new Date(t.created_at).toLocaleString()}
                </div>
              </li>
            ))}
            {tasks.data?.items.length === 0 && (
              <li className="p-6 text-center text-sm text-slate-500">No tasks yet.</li>
            )}
          </ul>
        </section>

        <section className="card">
          <header className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-800">
            <h2 className="font-medium">Recent files</h2>
            <Link to="/files" className="text-sm text-brand-600 hover:underline">
              See all
            </Link>
          </header>
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {files.data?.items.map((f) => (
              <li key={f.id} className="flex items-center gap-3 p-3 text-sm">
                <FileText className="h-4 w-4 text-slate-400" />
                <div className="min-w-0 flex-1 truncate">{f.filename}</div>
                <div className="text-xs text-slate-500">{formatBytes(f.size)}</div>
              </li>
            ))}
            {files.data?.items.length === 0 && (
              <li className="p-6 text-center text-sm text-slate-500">No files yet.</li>
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
