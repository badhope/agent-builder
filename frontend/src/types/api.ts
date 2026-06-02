export type Role = "admin" | "user";
export type UserPlan = "free" | "pro" | "enterprise";

export interface User {
  id: string;
  email: string;
  full_name?: string;
  role: Role;
  plan: UserPlan;
  is_active: boolean;
  is_admin: boolean;
  created_at?: string;
  avatar_url?: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  refresh_jti?: string;
  token_type?: string;
  expires_in?: number;
}

export interface FileMeta {
  id: string;
  owner_id: string;
  filename: string;
  content_type: string;
  size: number;
  purpose: "source" | "asset" | "avatar" | "output";
  sha256: string;
  storage_backend: "local" | "s3";
  storage_key: string;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
  expires_at?: string | null;
  scan_status: "pending" | "clean" | "infected" | "error" | "skipped";
}

export interface Task {
  id: string;
  owner_id: string;
  batch_id?: string | null;
  source_file_id: string;
  source_format: string;
  target_format: string;
  state:
    | "pending"
    | "queued"
    | "running"
    | "succeeded"
    | "failed"
    | "cancelled"
    | "expired";
  priority: number;
  options_json?: Record<string, unknown> | null;
  backend?: string | null;
  output_file_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  progress_pct: number;
  progress_message?: string | null;
  attempts: number;
  max_attempts: number;
  webhook_url?: string | null;
  webhook_delivered: boolean;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  expires_at?: string | null;
}

export interface Batch {
  id: string;
  owner_id: string;
  name?: string | null;
  state: "pending" | "running" | "succeeded" | "failed" | "cancelled" | "expired";
  total: number;
  succeeded: number;
  failed: number;
  created_at: string;
  finished_at?: string | null;
}

export interface BatchWithItems extends Batch {
  items: Task[];
}
