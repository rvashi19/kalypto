import { type PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@repo/ui";

const NAV = [
  { label: "Tools", href: "/tools" },
  { label: "HSN Finder", href: "/hsn" },
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
      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 md:px-8 md:py-6">
        <header className="mb-6 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70 shadow-lg shadow-slate-950/30 backdrop-blur">
          <div className="flex items-center justify-between gap-4 px-5 py-4">
            <div className="flex min-w-0 items-center gap-6">
              <Link
                to="/tools"
                className="flex min-w-0 items-center gap-3 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                <span
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-sm font-bold tracking-tight text-white"
                  aria-hidden="true"
                >
                  K
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-400">
                    KALYPTO
                  </p>
                  <p className="mt-0.5 truncate text-sm font-medium text-slate-200">
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
                      className={`rounded-lg px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
                        active
                          ? "bg-slate-800 text-white"
                          : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-100"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
            </div>

            <div className="flex shrink-0 items-center gap-3">
              <span className="hidden rounded-full border border-slate-700 bg-slate-800/50 px-3 py-1 text-xs capitalize text-slate-400 sm:block">
                {role.replaceAll("_", " ")}
              </span>
              <Button size="sm" variant="secondary" onClick={onLogout}>
                Sign out
              </Button>
            </div>
          </div>

          <nav
            className="flex gap-1 overflow-x-auto border-t border-slate-800 px-4 py-2 md:hidden"
            aria-label="Mobile navigation"
          >
            {NAV.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    active
                      ? "bg-slate-800 text-white"
                      : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-100"
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
