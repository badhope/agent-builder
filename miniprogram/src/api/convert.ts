import { api, uploadFile } from './client'
import type { Task, FileMeta, PaginatedResponse, ConversionFormat } from '@/types/api'

export const convertApi = {
  async upload(filePath: string, purpose: 'source' | 'asset' = 'source'): Promise<FileMeta> {
    return uploadFile(filePath, purpose)
  },

  async convert(sourceFileId: string, targetFormat: string, options?: Record<string, unknown>): Promise<Task> {
    const params = new URLSearchParams()
    params.set('source_file_id', sourceFileId)
    params.set('target_format', targetFormat)
    if (options) {
      Object.entries(options).forEach(([k, v]) => {
        params.set(k, String(v))
      })
    }
    return api.post<Task>(`/v1/convert?${params.toString()}`)
  },

  async listTasks(params?: { state?: string; limit?: number; offset?: number }): Promise<PaginatedResponse<Task>> {
    const qs = new URLSearchParams()
    if (params?.state) qs.set('state', params.state)
    if (params?.limit) qs.set('limit', String(params.limit))
    if (params?.offset) qs.set('offset', String(params.offset))
    const q = qs.toString()
    return api.get<PaginatedResponse<Task>>(`/v1/tasks${q ? '?' + q : ''}`)
  },

  async getTask(id: string): Promise<Task> {
    return api.get<Task>(`/v1/tasks/${id}`)
  },

  async retryTask(id: string): Promise<Task> {
    return api.post<Task>(`/v1/tasks/${id}/retry`)
  },

  async cancelTask(id: string): Promise<Task> {
    return api.post<Task>(`/v1/tasks/${id}/cancel`)
  },

  async getFormats(): Promise<{ formats: string[]; conversions: ConversionFormat[] }> {
    return api.get('/v1/formats')
  }
}