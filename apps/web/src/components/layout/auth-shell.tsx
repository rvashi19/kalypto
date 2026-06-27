import type { PropsWithChildren } from "react";

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
}: PropsWithChildren<{
  eyebrow: string;
  title: string;
  description: string;
}>) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,_rgba(34,211,238,0.14),_transparent_34%),radial-gradient(circle_at_84%_10%,_rgba(20,184,166,0.12),_transparent_28%),linear-gradient(135deg,_rgba(15,23,42,0.98),_rgba(2,6,23,0.96))]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/40 to-transparent" />

      <div className="relative mx-auto flex min-h-screen max-w-6xl flex-col items-center justify-center px-6 py-12 md:flex-row md:items-center md:gap-16">
        <div className="mb-10 hidden flex-1 space-y-8 md:mb-0 md:block">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3.5 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" aria-hidden="true" />
            <span className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200">
              {eyebrow}
            </span>
          </div>
          <div className="space-y-4">
            <p className="text-sm font-semibold uppercase tracking-[0.32em] text-slate-500">
              KALYPTO
            </p>
            <h1 className="max-w-xl text-4xl font-semibold tracking-[-0.035em] text-white md:text-5xl">
              {title}
            </h1>
            <p className="max-w-lg text-base leading-8 text-slate-300">{description}</p>
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <FeaturePill
              title="Document assurance"
              body="Check invoices, packing lists, shipping bills, and evidence before handoff."
            />
            <FeaturePill
              title="Incentive visibility"
              body="Track RoDTEP, Drawback, IGST refund, and claim-risk signals per shipment."
            />
            <FeaturePill
              title="Tenant-safe"
              body="Organization-scoped access, audit logs, and role controls from day one."
            />
          </div>
        </div>

        <div className="w-full max-w-sm flex-shrink-0">{children}</div>
      </div>
    </div>
  );
}

function FeaturePill({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-xl shadow-slate-950/10 backdrop-blur">
      <p className="font-medium text-slate-100">{title}</p>
      <p className="mt-1.5 leading-6 text-slate-400">{body}</p>
    </div>
  );
}
