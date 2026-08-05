import React from "react";

interface ApprovalBannerProps {
  onApprove: () => void;
  onDiscard: () => void;
}

export const ApprovalBanner: React.FC<ApprovalBannerProps> = ({
  onApprove,
  onDiscard,
}) => {
  return (
    <div className="flex items-center justify-between bg-amber-900/30 border-b border-amber-800/50 px-6 py-3">
      <div className="flex items-center space-x-3">
        <span className="flex h-6 w-6 items-center justify-center rounded-full border border-amber-600/60 bg-amber-600/20 text-[10px] font-mono font-bold text-amber-400">
          !
        </span>
        <span className="font-mono text-xs text-amber-200/90">
          Agent-generated SQL is pending review. Approve to execute or discard to keep current state.
        </span>
      </div>
      <div className="flex space-x-2">
        <button
          onClick={onDiscard}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 font-mono text-[10px] font-medium text-slate-300 transition hover:bg-slate-800"
        >
          Discard
        </button>
        <button
          onClick={onApprove}
          className="rounded-lg bg-emerald-600 px-3 py-1.5 font-mono text-[10px] font-bold text-white shadow transition hover:bg-emerald-500"
        >
          Approve & Run
        </button>
      </div>
    </div>
  );
};
