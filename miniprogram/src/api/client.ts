import Taro from '@tarojs/taro'

const API_BASE = 'http://localhost:8000/api'

let accessToken: string | null = null
let refreshToken: string | null = null

try {
  accessToken = Taro.getStorageSync('access_token') || null
  refreshToken = Taro.getStorageSync('refresh_token') || null
} catch {
  // ignore
}

export function getTokens() {
  return { accessToken, refreshToken }
}

export function setTokens(access: string, refresh?: string) {
  accessToken = access
  if (refresh) refreshToken = refresh
  try {
    Taro.setStorageSync('access_token', access)
    if (refresh) Taro.setStorageSync('refresh_token', refresh)
  } catch {
    // ignore
  }
}

export function clearTokens() {
  accessToken = null
  refreshToken = null
  try {
    Taro.removeStorageSync('access_token')
    Taro.removeStorageSync('refresh_token')
  } catch {
    // ignore
  }
}

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  data?: any
  contentType?: string
}

async function request<T = any>(options: RequestOptions): Promise<T> {
  const {
    url,
    method = 'GET',
    data,
    params,
    contentType = 'application/json'
  } = options

  const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`

  const header: Record<string, string> = {}
  if (contentType !== 'multipart/form-data') {
    header['Content-Type'] = contentType
  }
  if (accessToken) {
    header['Authorization'] = `Bearer ${accessToken}`
  }

  try {
    const res = await Taro.request({
      url: fullUrl,
      method,
      data,
      header,
      timeout: 30000
    })

    if (res.statusCode >= 200 && res.statusCode < 300) {
      return res.data as T
    }

    if (res.statusCode === 401) {
      const refreshed = await tryRefresh()
      if (refreshed) {
        if (accessToken) {
          header['Authorization'] = `Bearer ${accessToken}`
        }
        const retryRes = await Taro.request({
          url: fullUrl,
          method,
          data,
          header,
          timeout: 30000
        })
        if (retryRes.statusCode >= 200 && retryRes.statusCode < 300) {
          return retryRes.data as T
        }
      }
      clearTokens()
      Taro.redirectTo({ url: '/pages/login/index' })
      throw new Error('Authentication required')
    }

    const body = res.data as any
    const message = body?.message || body?.detail || 'Request failed'
    Taro.showToast({ title: message, icon: 'none', duration: 2000 })
    throw new Error(message)
  } catch (err: any) {
    if (err.errMsg?.includes('timeout')) {
      Taro.showToast({ title: 'Request timeout', icon: 'none' })
      throw new Error('Request timeout')
    }
    if (err.errMsg?.includes('fail')) {
      Taro.showToast({ title: 'Network error', icon: 'none' })
      throw new Error('Network error')
    }
    throw err
  }
}

let refreshing: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  if (refreshing) return refreshing
  if (!refreshToken) return false
  refreshing = (async () => {
    try {
      const res = await Taro.request({
        url: `${API_BASE}/v1/auth/refresh`,
        method: 'POST',
        data: { refresh_token: refreshToken },
        header: { 'Content-Type': 'application/json' },
        timeout: 10000
      })
      if (res.statusCode === 200) {
        const body = res.data as any
        setTokens(body.access_token, body.refresh_token || refreshToken)
        return true
      }
      return false
    } catch {
      return false
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

export async function uploadFile(
  filePath: string,
  purpose: 'source' | 'asset' | 'avatar' = 'source'
): Promise<any> {
  const header: Record<string, string> = {}
  if (accessToken) {
    header['Authorization'] = `Bearer ${accessToken}`
  }
  try {
    const res = await Taro.uploadFile({
      url: `${API_BASE}/v1/files/uploads?purpose=${purpose}`,
      filePath,
      name: 'file',
      header,
      timeout: 60000
    })
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return JSON.parse(res.data)
    }
    throw new Error('Upload failed')
  } catch (err: any) {
    Taro.showToast({ title: 'Upload failed', icon: 'none' })
    throw err
  }
}

export const api = {
  get: <T = any>(url: string) =>
    request<T>({ url, method: 'GET' }),
  post: <T = any>(url: string, data?: any) =>
    request<T>({ url, method: 'POST', data }),
  put: <T = any>(url: string, data?: any) =>
    request<T>({ url, method: 'PUT', data }),
  delete: <T = any>(url: string) =>
    request<T>({ url, method: 'DELETE' })
}