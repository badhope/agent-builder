import { api } from "./client";
import type { TokenPair, User } from "@/types/api";

export const authApi = {
  async login(email: string, password: string): Promise<TokenPair> {
    const { data } = await api.post<TokenPair>("/v1/auth/login", { email, password });
    return data;
  },
  async register(email: string, password: string, fullName?: string): Promise<TokenPair> {
    const { data } = await api.post<TokenPair>("/v1/auth/register", {
      email,
      password,
      full_name: fullName,
    });
    return data;
  },
  async me(): Promise<User> {
    const { data } = await api.get<User>("/v1/auth/me");
    return data;
  },
  async logout(refreshJti: string): Promise<void> {
    await api.post("/v1/auth/logout", { refresh_token_jti: refreshJti });
  },
};
