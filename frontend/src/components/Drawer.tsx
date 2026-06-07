import React from "react";
import { ChevronUp, ChevronDown } from "lucide-react";

interface DrawerProps {
  isOpen: boolean;
  onToggle: () => void;
  title: string;
  children: React.ReactNode;
  defaultHeight?: string;
}

export function Drawer({
  isOpen,
  onToggle,
  title,
  children,
  defaultHeight = "h-80",
}: DrawerProps) {
  return (
    <div
      className={`flex flex-col border-t border-slate-800 bg-slate-900 transition-all duration-300 ease-out ${
        isOpen ? defaultHeight : "h-12"
      } overflow-hidden`}
    >
      {/* Drawer Header/Toggle */}
      <button
        onClick={onToggle}
        className="flex flex-shrink-0 items-center justify-between border-b border-slate-800/60 bg-slate-950 px-4 py-3 transition-colors hover:bg-slate-900"
      >
        <span className="font-mono text-xs font-bold tracking-wider text-slate-400 uppercase">
          {title}
        </span>
        <div className="text-slate-500 transition-transform duration-300">
          {isOpen ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronUp className="h-4 w-4" />
          )}
        </div>
      </button>

      {/* Drawer Content */}
      {isOpen && (
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {children}
        </div>
      )}
    </div>
  );
}
