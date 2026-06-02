import { api } from "./client";
import type { Task, Batch, FileMeta } from "@/types/api";

export const convertApi = {
  async upload(file: File, purpose: "source" | "asset" | "avatar" = "source"): Promise<FileMeta> {
    const fd = new FormData();
    fd.append("file", file);
    const { data } = await api.post<FileMeta>("/v1/files/uploads", fd, {
      params: { purpose },
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        // Progress is exposed via the upload store
        const ev = new CustomEvent("upload-progress", {
          detail: { loaded: e.loaded, total: e.total ?? file.size, name: file.name },
        });
        window.dispatchEvent(ev);
      },
    });
    return data;
  },

  async convert(input: {
    sourceFileId: string;
    targetFormat: string;
    options?: Record<string, unknown>;
    webhookUrl?: string;
  }): Promise<Task> {
    const { data } = await api.post<Task>("/v1/convert", null, { params: input });
    return data;
  },

  async listTasks(params?: { state?: string; limit?: number; offset?: number }): Promise<{
    items: Task[];
    total: number;
  }> {
    const { data } = await api.get("/v1/tasks", { params });
    return data;
  },

  async getTask(id: string): Promise<Task> {
    const { data } = await api.get<Task>(`/v1/tasks/${id}`);
    return data;
  },

  async retryTask(id: string): Promise<Task> {
    const { data } = await api.post<Task>(`/v1/tasks/${id}/retry`);
    return data;
  },

  async cancelTask(id: string): Promise<Task> {
    const { data } = await api.post<Task>(`/v1/tasks/${id}/cancel`);
    return data;
  },

  async listBatches(): Promise<{ items: Batch[]; total: number }> {
    const { data } = await api.get("/v1/batches");
    return data;
  },

  async listFiles(): Promise<{ items: FileMeta[]; total: number }> {
    const { data } = await api.get("/v1/files");
    return data;
  },

  downloadUrl(fileId: string, withToken = false): string {
    return withToken
      ? `/v1/files/${fileId}/download`
      : `/v1/files/${fileId}/download`;
  },

  signedDownload(fileId: string, expiresIn = 3600) {
    return api
      .get<{ url: string; expires_in: number }>(`/v1/files/${fileId}/signed-url`, {
        params: { expires_in: expiresIn },
      })
      .then((r) => r.data);
  },
};
