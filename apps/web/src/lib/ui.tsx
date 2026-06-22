import { cn } from "@repo/ui";

// ── Shared form element classes ────────────────────────────────────────────────

export const inputCls =
  "flex h-10 w-full rounded-md border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 transition-colors placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-1 focus:ring-offset-slate-950 disabled:opacity-50";

export const selectCls = `${inputCls} cursor-pointer`;

// ── Status configuration ───────────────────────────────────────────────────────
// Always pair icon + label with colour — never colour alone.

export const DOC_STATUS_CFG = {
  pending: { icon: "◐", label: "Processing", cls: "text-amber-400" },
  extracted: { icon: "✓", label: "Done", cls: "text-emerald-400" },
  failed: { icon: "✕", label: "Failed", cls: "text-rose-400" },
} as const;

export const RISK_CFG = {
  low: { icon: "✓", label: "Low risk", cls: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" },
  medium: { icon: "◑", label: "Medium risk", cls: "bg-amber-500/10 text-amber-300 border-amber-500/20" },
  high: { icon: "⚠", label: "High risk", cls: "bg-orange-500/10 text-orange-300 border-orange-500/20" },
  critical: { icon: "✕", label: "Critical risk", cls: "bg-rose-500/10 text-rose-300 border-rose-500/20" },
} as const;

export const SEVERITY_CFG = {
  info: { icon: "ℹ", cls: "border-sky-500/20 bg-sky-500/8 text-sky-300" },
  warn: { icon: "⚠", cls: "border-amber-500/20 bg-amber-500/8 text-amber-300" },
  critical: { icon: "✕", cls: "border-rose-500/20 bg-rose-500/8 text-rose-300" },
} as const;

// ── Micro-components ───────────────────────────────────────────────────────────

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin h-4 w-4", className)}
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path
        className="opacity-80"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

export function AiBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-sky-500/20 bg-sky-500/8 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-sky-300">
      ✦ AI
    </span>
  );
}

export function ComingSoonBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-slate-600/40 bg-slate-800/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
      Coming soon
    </span>
  );
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p className="mt-1 flex items-center gap-1 text-xs text-rose-400" role="alert">
      <span aria-hidden="true">✕</span> {message}
    </p>
  );
}

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
      {children}
    </p>
  );
}

export function SkeletonCard() {
  return (
    <div className="rounded-xl border border-white/8 bg-slate-900/70 p-5 animate-pulse">
      <div className="h-4 w-2/3 rounded bg-slate-800" />
      <div className="mt-2 h-3 w-1/2 rounded bg-slate-800" />
      <div className="mt-4 grid grid-cols-3 gap-2">
        <div className="h-3 rounded bg-slate-800" />
        <div className="h-3 rounded bg-slate-800" />
        <div className="h-3 rounded bg-slate-800" />
      </div>
    </div>
  );
}
