import type { PropsWithChildren } from "react";

export function AuthShell({
  eyebrow,
  title,
  description,
  children
}: PropsWithChildren<{
  eyebrow: string;
  title: string;
  description: string;
}>) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.2),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(14,165,233,0.18),_transparent_24%)]" />
      <div className="relative mx-auto flex min-h-screen max-w-6xl items-center px-6 py-12">
        <div className="grid w-full gap-10 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-8">
            <div className="inline-flex rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-cyan-200">
              {eyebrow}
            </div>
            <div className="space-y-4">
              <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                {title}
              </h1>
              <p className="max-w-2xl text-base leading-7 text-slate-300">{description}</p>
            </div>
            <div className="grid gap-4 text-sm text-slate-300 sm:grid-cols-3">
              <FeaturePill title="Tenant-safe" body="Every business query is organization-scoped by design." />
              <FeaturePill title="Audited" body="Auth and repository activity is logged to an append-only trail." />
              <FeaturePill title="Phase-ready" body="The dashboard is set up for data ingestion next." />
            </div>
          </div>
          <div>{children}</div>
        </div>
      </div>
    </div>
  );
}

function FeaturePill({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur">
      <p className="font-medium text-slate-100">{title}</p>
      <p className="mt-2 text-slate-400">{body}</p>
    </div>
  );
}
