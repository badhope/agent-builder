import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { api } from "@/api/client";
import { Spinner } from "@/components/ui/Spinner";
import { KeyRound, Trash2, Copy, Check } from "lucide-react";
import type { ApiKeyRead } from "@/types/auth";

export default function ApiKeysPage() {
  const qc = useQueryClient();
  const [newName, setNewName] = useState("");
  const [plain, setPlain] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const list = useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => (await api.get<ApiKeyRead[]>("/v1/auth/api-keys")).data,
  });

  const create = useMutation({
    mutationFn: async (name: string) =>
      (await api.post<{ id: string; plain: string; scopes: string[] }>(
        "/v1/auth/api-keys",
        { name, scopes: ["convert:write", "files:read"] },
      )).data,
    onSuccess: (data) => {
      setPlain(data.plain);
      qc.invalidateQueries({ queryKey: ["api-keys"] });
      setNewName("");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const revoke = useMutation({
    mutationFn: async (id: string) => api.delete(`/v1/auth/api-keys/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  if (list.isLoading) return <Spinner fullscreen />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">API Keys</h1>

      {plain && (
        <div className="card border-amber-300 bg-amber-50 p-4 dark:border-amber-700 dark:bg-amber-900/20">
          <div className="text-sm font-medium text-amber-800 dark:text-amber-200">
            Save this key now — you won’t see it again.
          </div>
          <div className="mt-2 flex items-center gap-2">
            <code className="block flex-1 overflow-x-auto rounded bg-slate-900 p-2 text-xs text-slate-100">
              {plain}
            </code>
            <button
              className="btn-secondary"
              onClick={async () => {
                await navigator.clipboard.writeText(plain);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
          <button className="btn-ghost mt-2 text-xs" onClick={() => setPlain(null)}>
            I have stored this key
          </button>
        </div>
      )}

      <section className="card p-5">
        <h2 className="mb-3 font-medium">Create a key</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate(newName || "default");
          }}
          className="flex gap-2"
        >
          <input
            className="input"
            placeholder="Key name (e.g. CI)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <button className="btn-primary" disabled={create.isPending}>
            <KeyRound className="h-4 w-4" />
            Create
          </button>
        </form>
      </section>

      <section className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-900">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Prefix</th>
              <th className="px-3 py-2">Scopes</th>
              <th className="px-3 py-2">Created</th>
              <th className="px-3 py-2">Last used</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {list.data?.map((k) => (
              <tr key={k.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                <td className="px-3 py-2">{k.name}</td>
                <td className="px-3 py-2 font-mono text-xs">{k.prefix}…</td>
                <td className="px-3 py-2 text-xs">{k.scopes.join(", ")}</td>
                <td className="px-3 py-2 text-xs text-slate-500">
                  {new Date(k.created_at).toLocaleString()}
                </td>
                <td className="px-3 py-2 text-xs text-slate-500">
                  {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "—"}
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => revoke.mutate(k.id)}
                    disabled={k.revoked}
                    className="btn-ghost p-1 text-red-600 disabled:opacity-30"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
            {list.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-slate-500">
                  No API keys yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
