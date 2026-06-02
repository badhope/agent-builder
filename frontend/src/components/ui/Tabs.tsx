import { type ReactNode } from "react";
import { cn } from "@/utils/format";

interface Tab {
  id: string;
  label: string;
}

interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onChange: (id: string) => void;
  children?: ReactNode;
  className?: string;
}

export function Tabs({ tabs, activeTab, onChange, children, className }: TabsProps) {
  return (
    <div className={cn("w-full", className)}>
      <div className="flex border-b border-slate-200 dark:border-slate-700" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              "relative px-4 py-2 text-sm font-medium transition-colors",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
              activeTab === tab.id
                ? "text-brand-600 dark:text-brand-400"
                : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200",
            )}
          >
            {tab.label}
            {activeTab === tab.id && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-600 dark:bg-brand-400" />
            )}
          </button>
        ))}
      </div>
      {children && <div className="pt-4">{children}</div>}
    </div>
  );
}

export default Tabs;