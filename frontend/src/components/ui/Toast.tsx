import { Toaster } from "react-hot-toast";
import toast from "react-hot-toast";

export function Toast() {
  return (
    <Toaster
      position="top-right"
      gutter={8}
      toastOptions={{
        duration: 4000,
        style: {
          borderRadius: "8px",
          background: "var(--toast-bg, #fff)",
          color: "var(--toast-color, #1e293b)",
          fontSize: "14px",
          boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
        },
        success: {
          iconTheme: {
            primary: "#16a34a",
            secondary: "#fff",
          },
        },
        error: {
          iconTheme: {
            primary: "#dc2626",
            secondary: "#fff",
          },
        },
      }}
    />
  );
}

export { toast };

export default Toast;