import { create } from "zustand";

export interface UploadItem {
  id: string;
  file: File;
  progress: number;
  status: "queued" | "uploading" | "done" | "error";
  error?: string;
  fileId?: string;
}

interface UploadState {
  items: UploadItem[];
  add: (file: File) => string;
  update: (id: string, patch: Partial<UploadItem>) => void;
  remove: (id: string) => void;
  clear: () => void;
}

export const useUploadStore = create<UploadState>((set) => ({
  items: [],
  add: (file) => {
    const id = crypto.randomUUID();
    set((s) => ({ items: [...s.items, { id, file, progress: 0, status: "queued" }] }));
    return id;
  },
  update: (id, patch) =>
    set((s) => ({
      items: s.items.map((i) => (i.id === id ? { ...i, ...patch } : i)),
    })),
  remove: (id) => set((s) => ({ items: s.items.filter((i) => i.id !== id) })),
  clear: () => set({ items: [] }),
}));
