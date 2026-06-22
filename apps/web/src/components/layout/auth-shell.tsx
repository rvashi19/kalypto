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
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.12),_transparent_35%),radial-gradient(circle_at_bottom_right,_rgba(79,70,229,0.08),_transparent_30%)]" />

      <div className="relative mx-auto flex min-h-screen max-w-6xl flex-col items-center justify-center px-6 py-12 md:flex-row md:items-center md:gap-16">
        {/* Hero text — hidden on small screens */}
        <div className="mb-10 hidden flex-1 space-y-8 md:mb-0 md:block">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-indigo-400/20 bg-indigo-400/8 px-3 py-1">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" aria-hidden="true" />
            <span className="text-xs font-semibold uppercase tracking-widest text-indigo-300">
              {eyebrow}
            </span>
          </div>
          <div className="space-y-4">
            <h1 className="max-w-lg text-4xl font-semibold tracking-tight text-white">{title}</h1>
            <p className="max-w-md text-base leading-7 text-slate-400">{description}</p>
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <FeaturePill
              title="AI document audit"
              body="Cross-check invoices, packing lists, and shipping bills before customs submission."
            />
            <FeaturePill
              title="Incentive recovery"
              body="Estimate RoDTEP, Duty Drawback, and IGST refund eligibility for every shipment."
            />
            <FeaturePill
              title="Tenant-isolated"
              body="Every query is scoped to your organization. No data leaks between accounts."
            />
          </div>
        </div>

        {/* Auth card — full width on mobile */}
        <div className="w-full max-w-sm flex-shrink-0">{children}</div>
      </div>
    </div>
  );
}

function FeaturePill({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/4 p-4 backdrop-blur">
      <p className="font-medium text-slate-100">{title}</p>
      <p className="mt-1.5 text-slate-500">{body}</p>
    </div>
  );
}
