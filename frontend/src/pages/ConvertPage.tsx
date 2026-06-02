import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { api } from "@/api/client";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { Spinner } from "@/components/ui/Spinner";
import { useTaskProgress } from "@/hooks/useTaskProgress";
import { convertApi } from "@/api/convert";
import { ArrowRight, FileText, RefreshCw, AlertCircle } from "lucide-react";
import { formatBytes } from "@/utils/format";
import type { FileMeta, Task } from "@/types/api";

const COMMON_TARGETS = [
  "pdf", "docx", "html", "md", "txt", "png", "jpg", "json", "csv", "xlsx",
];

export default function ConvertPage() {
  const navigate = useNavigate();
  const formats = useQuery({
    queryKey: ["formats"],
    queryFn: async () => (await api.get<{ formats: string[] }>("/v1/formats")).data.formats,
    staleTime: 5 * 60 * 1000,
  });
  const [source, setSource] = useState<FileMeta | null>(null);
  const [target, setTarget] = useState("pdf");
  const [task, setTask] = useState<Task | null>(null);
  const [converting, setConverting] = useState(false);
  const progress = useTaskProgress(task?.id ?? null);

  useEffect(() => {
    if (progress && progress.task_id === task?.id) {
      setTask((t) => (t ? { ...t, state: progress.state as Task["state"], progress_pct: progress.progress_pct } : t));
    }
  }, [progress, task?.id]);

  const submit = async () => {
    if (!source) return;
    setConverting(true);
    try {
      const t = await convertApi.convert({
        sourceFileId: source.id,
        targetFormat: target,
      });
      setTask(t);
      toast.success("Conversion started");
    } catch (e) {
      toast.error((e as Error).message || "Conversion failed");
    } finally {
      setConverting(false);
    }
  };

  const handleNewConversion = () => {
    setTask(null);
    setSource(null);
  };

  if (formats.isLoading) return <Spinner fullscreen />;

  if (formats.isError) {
    return (
      <div className="card p-6 text-center">
        <AlertCircle className="mx-auto h-8 w-8 text-red-500" />
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          Failed to load supported formats.
        </p>
        <button
          onClick={() => formats.refetch()}
          className="btn-secondary mt-3"
        >
          <RefreshCw className="h-4 w-4" /> Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Convert a file</h1>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="mb-3 font-medium">1. Upload</h2>
          <FileDropzone
            onUploaded={async (id) => {
              const f = (await api.get<FileMeta>(`/v1/files/${id}`)).data;
              setSource(f);
            }}
          />
          {source && (
            <div className="mt-4 flex items-center gap-3 rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
              <FileText className="h-4 w-4 text-slate-400" />
              <div className="min-w-0 flex-1 truncate">{source.filename}</div>
              <div className="text-xs text-slate-500">{formatBytes(source.size)}</div>
            </div>
          )}
        </section>

        <section className="card p-5">
          <h2 className="mb-3 font-medium">2. Choose target format</h2>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            {COMMON_TARGETS.map((f) => (
              <button
                key={f}
                onClick={() => setTarget(f)}
                className={`btn ${target === f ? "btn-primary" : "btn-secondary"}`}
              >
                {f.toUpperCase()}
              </button>
            ))}
          </div>
          <details className="mt-4 text-sm">
            <summary className="cursor-pointer text-slate-500">All supported formats</summary>
            <div className="mt-2 flex flex-wrap gap-1">
              {formats.data?.map((f) => (
                <button
                  key={f}
                  onClick={() => setTarget(f)}
                  className={`badge ${
                    target === f
                      ? "bg-brand-100 text-brand-700"
                      : "bg-slate-100 text-slate-700"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </details>

          <button
            onClick={submit}
            disabled={!source || converting || !!task}
            className="btn-primary mt-5 w-full"
          >
            {converting ? (
              <>
                <Spinner size={14} /> Converting…
              </>
            ) : (
              <>
                Convert <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </section>
      </div>

      {task && (
        <section className="card p-5">
          <div className="flex items-center justify-between">
            <h2 className="mb-3 font-medium">3. Result</h2>
            {(task.state === "succeeded" || task.state === "failed" || task.state === "cancelled") && (
              <button onClick={handleNewConversion} className="btn-ghost text-sm">
                <RefreshCw className="h-3.5 w-3.5" /> New conversion
              </button>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`badge ${
                task.state === "succeeded"
                  ? "bg-emerald-100 text-emerald-700"
                  : task.state === "failed"
                    ? "bg-red-100 text-red-700"
                    : task.state === "cancelled"
                      ? "bg-slate-100 text-slate-700"
                      : "bg-amber-100 text-amber-700"
              }`}
            >
              {task.state}
            </span>
            <div className="min-w-0 flex-1 truncate text-sm">
              {task.source_format.toUpperCase()} → {task.target_format.toUpperCase()}
            </div>
            <button
              onClick={() => navigate(`/tasks`)}
              className="btn-ghost text-sm"
            >
              View details
            </button>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div
              className="h-full bg-brand-500 transition-all"
              style={{ width: `${task.progress_pct}%` }}
            />
          </div>
          {task.error_message && (
            <p className="mt-2 text-sm text-red-600">{task.error_message}</p>
          )}
        </section>
      )}
    </div>
  );
}
