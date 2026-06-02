import { cn } from "@/utils/format";

type ProgressSize = "sm" | "md";
type ProgressColor = "brand" | "green" | "red" | "amber";

interface ProgressBarProps {
  value?: number;
  size?: ProgressSize;
  color?: ProgressColor;
  showLabel?: boolean;
  animated?: boolean;
  className?: string;
}

const sizeClass: Record<ProgressSize, string> = {
  sm: "h-1.5",
  md: "h-2.5",
};

const colorClass: Record<ProgressColor, string> = {
  brand: "bg-brand-600",
  green: "bg-green-500",
  red: "bg-red-500",
  amber: "bg-amber-500",
};

export function ProgressBar({
  value,
  size = "md",
  color = "brand",
  showLabel = false,
  animated = false,
  className,
}: ProgressBarProps) {
  const isIndeterminate = value === undefined;

  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700",
            sizeClass[size],
          )}
          role="progressbar"
          aria-valuenow={isIndeterminate ? undefined : value}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          {isIndeterminate ? (
            <div
              className={cn(
                "h-full w-1/3 rounded-full",
                colorClass[color],
                animated && "animate-progress-indeterminate origin-left",
              )}
              style={
                animated
                  ? undefined
                  : {
                      animation: "progress-indeterminate 1.5s ease-in-out infinite",
                    }
              }
            />
          ) : (
            <div
              className={cn("h-full rounded-full transition-all duration-300 ease-out", colorClass[color])}
              style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
            />
          )}
        </div>
        {showLabel && !isIndeterminate && (
          <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
            {Math.round(value)}%
          </span>
        )}
      </div>
    </div>
  );
}

export default ProgressBar;