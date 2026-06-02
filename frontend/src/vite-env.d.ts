/// <reference types="vite/client" />
/// <reference types="vitest/globals" />

interface ImportMetaEnv {
  readonly VITE_API_BASE: string;
  readonly VITE_WS_BASE: string;
  readonly VITE_APP_NAME: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
