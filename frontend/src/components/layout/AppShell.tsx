import { useEffect, useRef } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  Files,
  KeyRound,
  ListTodo,
  Settings,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/stores/auth";
import { cn } from "@/utils/format";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, key: "dashboard" },
  { to: "/convert", icon: FileText, key: "convert" },
  { to: "/tasks", icon: ListTodo, key: "tasks" },
  { to: "/files", icon: Files, key: "files" },
  { to: "/settings", icon: Settings, key: "settings" },
  { to: "/settings/api-keys", icon: KeyRound, key: "apiKeys" },
] as const;

export function AppShell() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const sidebarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "[" && (e.metaKey || e.ctrlKey)) {
        sidebarRef.current?.classList.toggle("-translate-x-full");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="grid h-full grid-cols-[260px_1fr] bg-slate-50 dark:bg-slate-950">
      <aside
        ref={sidebarRef}
        className="flex flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
      >
        <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-4 dark:border-slate-800">
          <div className="grid h-8 w-8 place-items-center rounded-md bg-brand-600 text-white">
            <span className="font-bold">D</span>
          </div>
          <span className="font-semibold tracking-tight">DocFormatConverter</span>
        </div>

        <nav className="flex-1 space-y-1 p-3 text-sm">
          {navItems.map(({ to, icon: Icon, key }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 transition",
                  isActive
                    ? "bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-200"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
                )
              }
            >
              <Icon className="h-4 w-4" />
              <span>{t(`nav.${key}`)}</span>
            </NavLink>
          ))}
          {user?.is_admin && (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                cn(
                  "mt-4 flex items-center gap-3 rounded-md px-3 py-2 text-amber-700 transition",
                  "hover:bg-amber-50 dark:text-amber-300 dark:hover:bg-amber-900/30",
                  isActive && "bg-amber-50 dark:bg-amber-900/30",
                )
              }
            >
              <ShieldCheck className="h-4 w-4" />
              <span>{t("nav.admin")}</span>
            </NavLink>
          )}
        </nav>

        <div className="border-t border-slate-200 p-3 text-xs dark:border-slate-800">
          {user && (
            <div className="mb-2 flex items-center gap-2">
              <div className="grid h-8 w-8 place-items-center rounded-full bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-200">
                {user.email[0]?.toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{user.email}</div>
                <div className="text-slate-500 dark:text-slate-400">
                  {user.plan} · {user.role}
                </div>
              </div>
            </div>
          )}
          <button
            className="btn-ghost w-full justify-start"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            <LogOut className="h-4 w-4" />
            {t("auth.logout")}
          </button>
        </div>
      </aside>

      <main className="overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
