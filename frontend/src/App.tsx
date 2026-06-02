import { Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import { Spinner } from "./components/ui/Spinner";

const LandingPage = lazy(() => import("./pages/LandingPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ConvertPage = lazy(() => import("./pages/ConvertPage"));
const TasksPage = lazy(() => import("./pages/TasksPage"));
const FilesPage = lazy(() => import("./pages/FilesPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const ApiKeysPage = lazy(() => import("./pages/ApiKeysPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<Spinner fullscreen />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/convert" element={<ConvertPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/files" element={<FilesPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/settings/api-keys" element={<ApiKeysPage />} />
              <Route
                path="/admin/*"
                element={
                  <ProtectedRoute requireAdmin>
                    <AdminPage />
                  </ProtectedRoute>
                }
              />
            </Route>
          </Route>

          <Route path="/404" element={<NotFoundPage />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
