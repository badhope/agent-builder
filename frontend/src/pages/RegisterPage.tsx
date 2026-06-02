import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { useAuthStore } from "@/stores/auth";
import { Spinner } from "@/components/ui/Spinner";

const schema = z.object({
  email: z.string().email(),
  fullName: z.string().min(1, "Name is required").max(80).optional().or(z.literal("")),
  password: z
    .string()
    .min(12, "Use at least 12 characters")
    .regex(/[A-Z]/, "Add an uppercase letter")
    .regex(/[a-z]/, "Add a lowercase letter")
    .regex(/[0-9]/, "Add a digit")
    .regex(/[^A-Za-z0-9]/, "Add a symbol"),
});
type Form = z.infer<typeof schema>;

export default function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const registerUser = useAuthStore((s) => s.register);
  const [loading, setLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Form>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: Form) => {
    setLoading(true);
    try {
      await registerUser(data.email, data.password, data.fullName);
      navigate("/dashboard");
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
        <h1 className="text-xl font-semibold">{t("auth.register")}</h1>

        <div>
          <label className="text-sm font-medium">{t("auth.email")}</label>
          <input {...register("email")} type="email" className="input mt-1" />
          {errors.email && (
            <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
          )}
        </div>

        <div>
          <label className="text-sm font-medium">Full name (optional)</label>
          <input {...register("fullName")} type="text" className="input mt-1" />
        </div>

        <div>
          <label className="text-sm font-medium">{t("auth.password")}</label>
          <input
            {...register("password")}
            type="password"
            autoComplete="new-password"
            className="input mt-1"
          />
          {errors.password && (
            <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
          )}
          <p className="mt-1 text-xs text-slate-500">
            12+ chars, mixed case, a digit and a symbol.
          </p>
        </div>

        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? <Spinner size={16} /> : t("auth.submit")}
        </button>

        <div className="text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link to="/login" className="text-brand-600 hover:underline">
            {t("auth.login")}
          </Link>
        </div>
      </form>
    </div>
  );
}
