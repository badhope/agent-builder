import { cn } from "@/utils/format";

export function Spinner({
  size = 16,
  className,
  fullscreen = false,
}: {
  size?: number;
  className?: string;
  fullscreen?: boolean;
}) {
  const inner = (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        "inline-block animate-spin rounded-full border-2 border-slate-300 border-t-brand-600",
        className,
      )}
      style={{ width: size, height: size }}
    />
  );
  if (fullscreen) {
    return (
      <div className="grid h-full place-items-center bg-slate-50 dark:bg-slate-950">
        {inner}
      </div>
    );
  }
  return inner;
}
