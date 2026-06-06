import type { PropsWithChildren } from "react";

import { Button } from "@repo/ui";

export function DashboardShell({
  organizationName,
  role,
  onLogout,
  children
}: PropsWithChildren<{
  organizationName: string;
  role: string;
  onLogout: () => void;
}>) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-6 py-6">
        <header className="mb-8 flex flex-col gap-4 rounded-3xl border border-white/10 bg-slate-900/70 p-6 backdrop-blur md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-cyan-300">Phase 0 foundation</p>
            <h1 className="mt-2 text-2xl font-semibold">{organizationName}</h1>
            <p className="mt-1 text-sm text-slate-400">Signed in as {role.replaceAll("_", " ")}</p>
          </div>
          <Button variant="secondary" onClick={onLogout}>
            Log out
          </Button>
        </header>
        {children}
      </div>
    </div>
  );
}
