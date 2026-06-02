import { type ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";

interface Props {
  children?: ReactNode;
  requireAdmin?: boolean;
}

export function ProtectedRoute({ children, requireAdmin }: Props) {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (requireAdmin && !user?.is_admin) {
    return <Navigate to="/dashboard" replace />;
  }
  return children ? <>{children}</> : <Outlet />;
}
