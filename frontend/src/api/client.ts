import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
} from "axios";
import toast from "react-hot-toast";
import { useAuthStore } from "@/stores/auth";

const baseURL = import.meta.env.VITE_API_BASE ?? "";

export const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((cfg) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    cfg.headers.set("Authorization", `Bearer ${token}`);
  }
  return cfg;
});

interface ApiErrorBody {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
}

api.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError<ApiErrorBody>) => {
    const status = error.response?.status;
    const body = error.response?.data;
    const code = body?.code ?? "unknown_error";
    const message = body?.message ?? error.message;

    if (status === 401) {
      // Try refresh once
      const refreshed = await tryRefresh();
      if (refreshed && error.config) {
        return api.request(error.config as AxiosRequestConfig);
      }
      useAuthStore.getState().clear();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    } else if (status && status >= 500) {
      toast.error("Server error. Please try again.");
    } else if (status === 429) {
      toast.error("Too many requests. Slow down.");
    } else if (status && status >= 400 && body?.message) {
      toast.error(message);
    }

    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.debug(`[api] ${code}: ${message}`);
    }
    return Promise.reject(Object.assign(error, { code, message }));
  },
);

let refreshing: Promise<boolean> | null = null;
async function tryRefresh(): Promise<boolean> {
  if (refreshing) return refreshing;
  const refresh = useAuthStore.getState().refreshToken;
  if (!refresh) return false;
  refreshing = (async () => {
    try {
      const r = await axios.post(`${baseURL}/v1/auth/refresh`, { refresh_token: refresh });
      useAuthStore.getState().setTokens(r.data.access_token, r.data.refresh_token ?? refresh);
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}
