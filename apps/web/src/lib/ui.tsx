import { cn } from "@repo/ui";

export const inputCls =
  "flex h-11 w-full rounded-lg border border-[#b7b9be] bg-white px-3.5 py-2 text-sm text-[#101214] transition-colors placeholder:text-[#42526e]/60 focus:border-[#1868db] focus:outline-none focus:ring-2 focus:ring-[#1868db]/25 focus:ring-offset-2 focus:ring-offset-white disabled:opacity-50";

export const selectCls = `${inputCls} cursor-pointer`;

export const DOC_STATUS_CFG = {
  pending: { icon: "...", label: "Processing", cls: "text-[#fca700]" },
  extracted: { icon: "OK", label: "Done", cls: "text-[#36b37e]" },
  failed: { icon: "!", label: "Failed", cls: "text-[#de350b]" },
} as const;

export const RISK_CFG = {
  low: { icon: "OK", label: "Low risk", cls: "bg-[#e3fcef] text-[#006644] border-[#abf5d1]" },
  medium: { icon: "Med", label: "Medium risk", cls: "bg-[#fff7d6] text-[#7a5300] border-[#f5cd47]" },
  high: { icon: "High", label: "High risk", cls: "bg-[#fff0b3] text-[#7a5300] border-[#fca700]" },
  critical: { icon: "Crit", label: "Critical risk", cls: "bg-[#ffebe6] text-[#bf2600] border-[#ffbdad]" },
} as const;

export const SEVERITY_CFG = {
  info: { icon: "Info", cls: "border-[#b3d4ff] bg-[#e9f2fe] text-[#1868db]" },
  warn: { icon: "Warn", cls: "border-[#f5cd47] bg-[#fff7d6] text-[#7a5300]" },
  critical: { icon: "Crit", cls: "border-[#ffbdad] bg-[#ffebe6] text-[#bf2600]" },
} as const;

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("h-4 w-4 animate-spin", className)}
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
    <span className="inline-flex items-center gap-1 rounded-full bg-[#e9f2fe] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#1868db]">
      AI assist
    </span>
  );
}

export function ComingSoonBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[#f0f1f2] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#42526e]">
      Coming soon
    </span>
  );
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p className="mt-1 text-xs text-[#bf2600]" role="alert">
      {message}
    </p>
  );
}

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[#42526e]">
      {children}
    </p>
  );
}

export function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-[20px] border border-[#f0f1f2] bg-white p-5 shadow-[rgba(9,30,66,0.31)_0_0_1px_0,rgba(9,30,66,0.25)_0_1px_1px_0]">
      <div className="h-4 w-2/3 rounded bg-[#f0f1f2]" />
      <div className="mt-2 h-3 w-1/2 rounded bg-[#f0f1f2]" />
      <div className="mt-4 grid grid-cols-3 gap-2">
        <div className="h-3 rounded bg-[#f0f1f2]" />
        <div className="h-3 rounded bg-[#f0f1f2]" />
        <div className="h-3 rounded bg-[#f0f1f2]" />
      </div>
    </div>
  );
}
