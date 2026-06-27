import { type PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@repo/ui";

const NAV = [
  { label: "Tools", href: "/tools" },
  { label: "Shipments", href: "/shipments" },
  { label: "Compliance", href: "/compliance" },
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
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_10%_0%,rgba(34,211,238,0.08),transparent_28rem),radial-gradient(circle_at_90%_15%,rgba(20,184,166,0.07),transparent_30rem)]" />
      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 md:px-8 md:py-6">
        <header className="mb-6 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/80 shadow-2xl shadow-slate-950/20 backdrop-blur">
          <div className="flex items-center justify-between gap-4 px-5 py-4">
            <div className="flex min-w-0 items-center gap-6">
              <Link
                to="/tools"
                className="flex min-w-0 items-center gap-3 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
              >
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-sm font-bold tracking-tight text-cyan-100"
                  aria-hidden="true"
                >
                  K
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-200">
                    KALYPTO
                  </p>
                  <p className="mt-0.5 truncate text-sm font-medium text-slate-300">
                    {organizationName}
                  </p>
                </div>
              </Link>

              <nav className="hidden gap-1 md:flex" aria-label="Main navigation">
                {NAV.map((item) => {
                  const active = pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      to={item.href}
                      className={`rounded-xl px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${
                        active
                          ? "bg-cyan-300/10 text-cyan-100"
                          : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
            </div>

            <div className="flex shrink-0 items-center gap-3">
              <span className="hidden rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs capitalize text-slate-400 sm:block">
                {role.replaceAll("_", " ")}
              </span>
              <Button size="sm" variant="secondary" onClick={onLogout}>
                Sign out
              </Button>
            </div>
          </div>

          <nav
            className="flex gap-1 overflow-x-auto border-t border-white/10 px-4 py-2 md:hidden"
            aria-label="Mobile navigation"
          >
            {NAV.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  className={`whitespace-nowrap rounded-xl px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-cyan-300/10 text-cyan-100"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>

        <main className="flex-1 pb-10">{children}</main>
      </div>
    </div>
  );
}
