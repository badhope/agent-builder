import { useState, useCallback, useEffect } from 'react'
import { authApi } from '@/api/auth'
import { getTokens, clearTokens } from '@/api/client'
import type { UserProfile } from '@/types/api'

interface AuthState {
  user: UserProfile | null
  isLoggedIn: boolean
  isLoading: boolean
}

let globalState: AuthState = {
  user: null,
  isLoggedIn: false,
  isLoading: true
}

const listeners: Set<() => void> = new Set()

function notify() {
  listeners.forEach(fn => fn())
}

export function useAuth() {
  const [, setTick] = useState(0)

  useEffect(() => {
    const fn = () => setTick(t => t + 1)
    listeners.add(fn)
    return () => { listeners.delete(fn) }
  }, [])

  useEffect(() => {
    if (globalState.isLoading) {
      checkAuth()
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    globalState = { ...globalState, isLoading: true }
    notify()
    try {
      const data = await authApi.login(email, password)
      globalState = { user: data.user, isLoggedIn: true, isLoading: false }
      notify()
      return data
    } catch (err) {
      globalState = { ...globalState, isLoading: false }
      notify()
      throw err
    }
  }, [])

  const register = useCallback(async (email: string, password: string, name?: string) => {
    globalState = { ...globalState, isLoading: true }
    notify()
    try {
      const data = await authApi.register(email, password, name)
      globalState = { user: data.user, isLoggedIn: true, isLoading: false }
      notify()
      return data
    } catch (err) {
      globalState = { ...globalState, isLoading: false }
      notify()
      throw err
    }
  }, [])

  const logout = useCallback(() => {
    authApi.logout()
    globalState = { user: null, isLoggedIn: false, isLoading: false }
    notify()
  }, [])

  return {
    ...globalState,
    login,
    register,
    logout
  }
}

async function checkAuth() {
  const { accessToken } = getTokens()
  if (!accessToken) {
    globalState = { user: null, isLoggedIn: false, isLoading: false }
    notify()
    return
  }
  try {
    const user = await authApi.getProfile()
    globalState = { user, isLoggedIn: true, isLoading: false }
    notify()
  } catch {
    clearTokens()
    globalState = { user: null, isLoggedIn: false, isLoading: false }
    notify()
  }
}