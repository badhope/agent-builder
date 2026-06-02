import { cn } from "@/utils/format";

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  className?: string;
}

export function Switch({ checked, onChange, label, disabled, className }: SwitchProps) {
  return (
    <label
      className={cn(
        "inline-flex cursor-pointer items-center gap-2",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2",
          checked ? "bg-brand-600" : "bg-slate-300 dark:bg-slate-600",
        )}
      >
        <span
          className={cn(
            "inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform",
            checked ? "translate-x-[18px]" : "translate-x-[2px]",
          )}
        />
      </button>
      {label && (
        <span className="text-sm text-slate-700 dark:text-slate-200 select-none">
          {label}
        </span>
      )}
    </label>
  );
}

export default Switch;