import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { TokenPair, User } from "@/types/api";
import { authApi } from "@/api/auth";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  refreshJti: string | null;
  user: User | null;
  loading: boolean;
  setTokens: (access: string, refresh: string) => void;
  setUser: (u: User | null) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      refreshJti: null,
      user: null,
      loading: false,

      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
      setUser: (user) => set({ user }),

      login: async (email, password) => {
        set({ loading: true });
        try {
          const tokens: TokenPair = await authApi.login(email, password);
          set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
          const me = await authApi.me();
          set({ user: me });
        } finally {
          set({ loading: false });
        }
      },

      register: async (email, password, fullName) => {
        set({ loading: true });
        try {
          const tokens: TokenPair = await authApi.register(email, password, fullName);
          set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
          const me = await authApi.me();
          set({ user: me });
        } finally {
          set({ loading: false });
        }
      },

      logout: async () => {
        const jti = get().refreshJti;
        try {
          if (jti) await authApi.logout(jti);
        } catch {
          /* ignore */
        }
        set({ accessToken: null, refreshToken: null, user: null, refreshJti: null });
      },

      clear: () =>
        set({ accessToken: null, refreshToken: null, user: null, refreshJti: null }),
    }),
    {
      name: "docconv.auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
        refreshJti: s.refreshJti,
      }),
    },
  ),
);
