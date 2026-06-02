import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { useAuthStore } from "@/stores/auth";
import { Spinner } from "@/components/ui/Spinner";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});
type Form = z.infer<typeof schema>;

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((s) => s.login);
  const [loading, setLoading] = useState(false);
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? "/dashboard";

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Form>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: Form) => {
    setLoading(true);
    try {
      await login(data.email, data.password);
      navigate(from, { replace: true });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-full place-items-center p-6">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="card w-full max-w-sm space-y-4 p-6"
      >
        <h1 className="text-xl font-semibold">{t("auth.login")}</h1>

        <div>
          <label className="text-sm font-medium">{t("auth.email")}</label>
          <input
            {...register("email")}
            type="email"
            autoComplete="email"
            className="input mt-1"
          />
          {errors.email && (
            <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
          )}
        </div>

        <div>
          <label className="text-sm font-medium">{t("auth.password")}</label>
          <input
            {...register("password")}
            type="password"
            autoComplete="current-password"
            className="input mt-1"
          />
          {errors.password && (
            <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
          )}
        </div>

        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? <Spinner size={16} /> : t("auth.submit")}
        </button>

        <div className="text-center text-sm text-slate-500">
          {t("auth.register")}?{" "}
          <Link to="/register" className="text-brand-600 hover:underline">
            Sign up
          </Link>
        </div>
      </form>
    </div>
  );
}
