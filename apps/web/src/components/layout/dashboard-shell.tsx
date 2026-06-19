import { type PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@repo/ui";

const NAV = [
  { label: "Shipments", href: "/shipments" },
  { label: "Dashboard", href: "/dashboard" },
];

export function DashboardShell({
  organizationName,
  role,
  onLogout,
  children,
}: PropsWithChildren<{ organizationName: string; role: string; onLogout: () => void }>) {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 md:px-6 md:py-6">
        <header className="mb-6 flex flex-col gap-4 rounded-2xl border border-white/10 bg-slate-900/70 px-5 py-4 backdrop-blur md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">ExportPilot</p>
              <h1 className="mt-0.5 text-lg font-semibold">{organizationName}</h1>
            </div>
            <nav className="hidden gap-1 md:flex">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    pathname.startsWith(item.href)
                      ? "bg-cyan-500/15 text-cyan-300"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500 capitalize">{role.replaceAll("_", " ")}</span>
            <Button variant="secondary" onClick={onLogout}>Sign out</Button>
          </div>
        </header>
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
