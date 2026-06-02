import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Spinner } from "@/components/ui/Spinner";
import { Users, FileText, ListTodo, Activity } from "lucide-react";

interface Stats {
  users: number;
  tasks: { total: number; pending: number; running: number };
  files: number;
  workers_active: number | null;
}

export default function AdminPage() {
  const stats = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: async () => (await api.get<Stats>("/v1/admin/stats")).data,
    refetchInterval: 5_000,
  });

  if (stats.isLoading) return <Spinner fullscreen />;

  const cards = [
    { icon: Users, label: "Users", value: stats.data?.users },
    { icon: ListTodo, label: "Tasks total", value: stats.data?.tasks.total },
    { icon: Activity, label: "Tasks pending", value: stats.data?.tasks.pending },
    { icon: FileText, label: "Files", value: stats.data?.files },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Admin</h1>
      <div className="grid gap-4 sm:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} className="card p-4">
            <div className="text-xs uppercase text-slate-500">{c.label}</div>
            <div className="text-2xl font-semibold">{c.value ?? "—"}</div>
          </div>
        ))}
      </div>
      <div className="card p-4 text-sm text-slate-500">
        Active workers:{" "}
        <span className="font-mono">{stats.data?.workers_active ?? "?"}</span>
      </div>
    </div>
  );
}
