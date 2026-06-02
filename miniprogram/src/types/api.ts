export interface Task {
  id: string
  owner_id: string
  state: string
  source_format: string
  target_format: string
  source_filename: string
  output_file_id?: string
  output_format?: string
  output_size?: number
  progress_pct?: number
  progress_message?: string
  error_code?: string
  error_message?: string
  backend?: string
  priority: string
  attempts: number
  max_attempts: number
  queued_at?: string
  started_at?: string
  finished_at?: string
  expires_at?: string
  created_at: string
  updated_at: string
}

export interface FileMeta {
  id: string
  filename: string
  format?: string
  content_type?: string
  size: number
  storage_backend: string
  purpose: string
  scan_status: string
  created_at: string
  expires_at?: string
}

export interface Batch {
  id: string
  owner_id: string
  state: string
  total: number
  completed: number
  failed: number
  format: string
  created_at: string
}

export interface UserProfile {
  id: string
  email: string
  name?: string
  avatar_url?: string
  role: string
  quota_total: number
  quota_used: number
  created_at: string
}

export interface ApiError {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
}

export interface ConversionFormat {
  source: string
  target: string
  quality: number
  backend: string
  estimated_time_s: number
}

export interface FormatsResponse {
  formats: string[]
  conversions: ConversionFormat[]
  graph: {
    nodes: string[]
    edges: Array<{ source: string; target: string; quality: number }>
  }
}