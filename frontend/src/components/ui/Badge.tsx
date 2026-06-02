import { type ReactNode } from "react";
import { cn } from "@/utils/format";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info";

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const variantClass: Record<BadgeVariant, string> = {
  default:
    "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  success: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  warning: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  danger: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  info: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
};

export function Badge({ variant = "default", children, className }: BadgeProps) {
  return (
    <span className={cn("badge", variantClass[variant], className)}>
      {children}
    </span>
  );
}

export default Badge;