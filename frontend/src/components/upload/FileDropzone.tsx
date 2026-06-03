import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud } from "lucide-react";
import { useUploadStore } from "@/stores/upload";
import { convertApi } from "@/api/convert";

// Hard cap is 100 MB. The server enforces the same limit but we check
// here so the user gets instant feedback instead of a 30s upload
// followed by a 413. If we ever need per-plan limits, lift this to
// a config and read from the user's profile.
const MAX_BYTES = 100 * 1024 * 1024;

// TODO: when we add chunked / resumable uploads, the per-file loop
// here is the wrong shape. We need:
//   1. POST /uploads/init -> upload_id, chunk_size
//   2. PUT /uploads/{id}/part?seq=N  (parallel, retried)
//   3. POST /uploads/{id}/complete
// For files under the cap the current single-shot POST is fine.
// For files over the cap, we will 413 today. The product ask is
// "files up to 5 GB on enterprise"; tracked in tasks.md.
export function FileDropzone({ onUploaded }: { onUploaded?: (id: string) => void }) {
  const add = useUploadStore((s) => s.add);
  const update = useUploadStore((s) => s.update);
  const items = useUploadStore((s) => s.items);

  const onDrop = useCallback(
    async (files: File[]) => {
      for (const f of files) {
        if (f.size > MAX_BYTES) {
          update(add(f), { status: "error", error: "File exceeds 100 MB" });
          continue;
        }
        const id = add(f);
        update(id, { status: "uploading" });
        try {
          const meta = await convertApi.upload(f);
          update(id, { status: "done", progress: 100, fileId: meta.id });
          onUploaded?.(meta.id);
        } catch (e) {
          update(id, { status: "error", error: (e as Error).message });
        }
      }
    },
    [add, update, onUploaded],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    maxSize: MAX_BYTES,
  });

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={[
          "card flex cursor-pointer flex-col items-center justify-center gap-2 p-8 text-center transition",
          isDragActive
            ? "border-brand-500 bg-brand-50 dark:bg-brand-900/20"
            : "hover:border-brand-400",
        ].join(" ")}
      >
        <input {...getInputProps()} />
        <UploadCloud className="h-10 w-10 text-brand-500" />
        <div className="text-sm">
          {isDragActive ? (
            <span>Drop the files here…</span>
          ) : (
            <span>Drag &amp; drop, or click to select files (≤ 100 MB each)</span>
          )}
        </div>
      </div>
      {items.length > 0 && (
        <ul className="card divide-y divide-slate-200 dark:divide-slate-800">
          {items.map((it) => (
            <li key={it.id} className="flex items-center gap-3 p-3 text-sm">
              <div className="min-w-0 flex-1 truncate">{it.file.name}</div>
              <div className="w-40">
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                  <div
                    className="h-full bg-brand-500"
                    style={{ width: `${it.progress}%` }}
                  />
                </div>
              </div>
              <div
                className={
                  it.status === "error"
                    ? "text-red-600"
                    : it.status === "done"
                      ? "text-emerald-600"
                      : "text-slate-500"
                }
              >
                {it.status}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
