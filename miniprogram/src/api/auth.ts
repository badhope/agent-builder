import { api, setTokens, clearTokens } from './client'
import type { UserProfile } from '@/types/api'

export const authApi = {
  async login(email: string, password: string): Promise<{ access_token: string; refresh_token: string; user: UserProfile }> {
    const data = await api.post<{ access_token: string; refresh_token: string; user: UserProfile }>('/v1/auth/login', { email, password })
    setTokens(data.access_token, data.refresh_token)
    return data
  },

  async register(email: string, password: string, name?: string): Promise<{ access_token: string; refresh_token: string; user: UserProfile }> {
    const data = await api.post<{ access_token: string; refresh_token: string; user: UserProfile }>('/v1/auth/register', { email, password, name })
    setTokens(data.access_token, data.refresh_token)
    return data
  },

  async getProfile(): Promise<UserProfile> {
    return api.get<UserProfile>('/v1/users/me')
  },

  logout() {
    clearTokens()
  }
}