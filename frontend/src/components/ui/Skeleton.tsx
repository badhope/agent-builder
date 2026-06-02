import { cn } from "@/utils/format";

type SkeletonVariant = "text" | "circular" | "rectangular";

interface SkeletonProps {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
  className?: string;
}

const variantClass: Record<SkeletonVariant, string> = {
  text: "h-4 rounded",
  circular: "rounded-full",
  rectangular: "rounded-md",
};

export function Skeleton({
  variant = "text",
  width,
  height,
  className,
}: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse bg-slate-200 dark:bg-slate-700",
        variant === "text" && !height && "h-4",
        variant === "circular" && !width && !height && "h-10 w-10",
        variantClass[variant],
        className,
      )}
      style={{ width, height }}
    />
  );
}

export default Skeleton;