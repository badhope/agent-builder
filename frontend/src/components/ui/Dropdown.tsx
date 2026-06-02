import { useState, useRef, useEffect, type ReactNode } from "react";
import { cn } from "@/utils/format";

interface DropdownItem {
  label: string;
  onClick: () => void;
  icon?: ReactNode;
  disabled?: boolean;
  divider?: never;
}

interface DropdownDivider {
  divider: true;
  label?: never;
  onClick?: never;
  icon?: never;
  disabled?: never;
}

type DropdownEntry = DropdownItem | DropdownDivider;

type DropdownAlign = "left" | "right";

interface DropdownProps {
  trigger: ReactNode;
  items: DropdownEntry[];
  align?: DropdownAlign;
  className?: string;
}

function isDivider(item: DropdownEntry): item is DropdownDivider {
  return "divider" in item && item.divider === true;
}

const alignClass: Record<DropdownAlign, string> = {
  left: "left-0",
  right: "right-0",
};

export function Dropdown({ trigger, items, align = "left", className }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  useEffect(() => {
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) {
      document.addEventListener("keydown", handleEscape);
    }
    return () => document.removeEventListener("keydown", handleEscape);
  }, [open]);

  return (
    <div ref={ref} className={cn("relative inline-block", className)}>
      <div onClick={() => setOpen((prev) => !prev)} className="cursor-pointer">
        {trigger}
      </div>
      {open && (
        <div
          className={cn(
            "absolute z-40 mt-1 min-w-[160px] overflow-hidden rounded-md border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900",
            alignClass[align],
          )}
          role="menu"
        >
          {items.map((item, i) =>
            isDivider(item) ? (
              <hr
                key={`divider-${i}`}
                className="my-1 border-slate-200 dark:border-slate-700"
              />
            ) : (
              <button
                key={`${item.label}-${i}`}
                role="menuitem"
                disabled={item.disabled}
                onClick={() => {
                  if (!item.disabled) {
                    item.onClick();
                    setOpen(false);
                  }
                }}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm transition-colors",
                  item.disabled
                    ? "cursor-not-allowed text-slate-400 dark:text-slate-500"
                    : "text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800",
                )}
              >
                {item.icon && <span className="h-4 w-4">{item.icon}</span>}
                {item.label}
              </button>
            ),
          )}
        </div>
      )}
    </div>
  );
}

export default Dropdown;