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
    <div className="atlassian-shell min-h-screen">
      <div className="atlassian-container flex min-h-screen flex-col items-center justify-center gap-8 py-10 lg:flex-row lg:gap-12">
        <section className="atlassian-dark-panel w-full px-8 py-10 md:px-12 md:py-14 lg:min-h-[640px] lg:flex-1">
          <div className="atlassian-confetti" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
          </div>
          <div className="relative z-10 flex h-full flex-col justify-between gap-12">
            <div className="space-y-8">
              <div className="inline-flex items-center rounded-full bg-white/10 px-4 py-2">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-white">
                  {eyebrow}
                </span>
              </div>
              <div className="space-y-5">
                <p className="text-sm font-semibold uppercase tracking-[0.32em] text-white/60">
                  KALYPTO
                </p>
                <h1 className="font-display max-w-2xl text-4xl font-medium leading-[1.05] tracking-normal text-white md:text-6xl">
                  {title}
                </h1>
                <p className="max-w-xl text-base leading-8 text-white/80">{description}</p>
              </div>
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
        </section>

        <div className="w-full max-w-md flex-shrink-0">{children}</div>
      </div>
    </div>
  );
}

function FeaturePill({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-[20px] border border-white/10 bg-white/[0.06] p-4">
      <p className="font-medium text-white">{title}</p>
      <p className="mt-1.5 leading-6 text-white/65">{body}</p>
    </div>
  );
}
