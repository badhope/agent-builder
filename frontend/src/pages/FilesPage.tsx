import { useQuery } from "@tanstack/react-query";
import { convertApi } from "@/api/convert";
import { Spinner } from "@/components/ui/Spinner";
import { FileText, Download } from "lucide-react";
import { formatBytes } from "@/utils/format";

export default function FilesPage() {
  const files = useQuery({
    queryKey: ["files"],
    queryFn: () => convertApi.listFiles(),
  });

  if (files.isLoading) return <Spinner fullscreen />;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Files</h1>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-900">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Size</th>
              <th className="px-3 py-2">Scan</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {files.data?.items.map((f) => (
              <tr key={f.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-slate-400" />
                    <span className="truncate">{f.filename}</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-xs">{f.content_type}</td>
                <td className="px-3 py-2 text-xs">{formatBytes(f.size)}</td>
                <td className="px-3 py-2">
                  <span
                    className={`badge ${
                      f.scan_status === "clean"
                        ? "bg-emerald-100 text-emerald-700"
                        : f.scan_status === "infected"
                          ? "bg-red-100 text-red-700"
                          : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {f.scan_status}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-slate-500">
                  {new Date(f.created_at).toLocaleString()}
                </td>
                <td className="px-3 py-2 text-right">
                  <a
                    href={convertApi.downloadUrl(f.id)}
                    className="btn-ghost p-1"
                    title="Download"
                  >
                    <Download className="h-4 w-4" />
                  </a>
                </td>
              </tr>
            ))}
            {files.data?.items.length === 0 && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-slate-500">
                  No files yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
