import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/api/client";
import type { User } from "@/types/api";

const schema = z.object({
  fullName: z.string().min(1).max(80).optional(),
  avatarUrl: z.string().url().optional(),
});
type Form = z.infer<typeof schema>;

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const { register, handleSubmit } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { fullName: user?.full_name ?? "", avatarUrl: user?.avatar_url ?? "" },
  });

  const onSubmit = async (data: Form) => {
    try {
      const r = await api.patch<User>("/v1/users/me", data);
      setUser(r.data);
      toast.success("Saved.");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <form onSubmit={handleSubmit(onSubmit)} className="card max-w-lg space-y-4 p-6">
        <div>
          <label className="text-sm font-medium">Full name</label>
          <input {...register("fullName")} className="input mt-1" />
        </div>
        <div>
          <label className="text-sm font-medium">Avatar URL</label>
          <input {...register("avatarUrl")} className="input mt-1" />
        </div>
        <button className="btn-primary" type="submit">Save</button>
      </form>
    </div>
  );
}
