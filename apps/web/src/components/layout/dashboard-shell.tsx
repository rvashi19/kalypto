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
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-4 md:px-8 md:py-6">
        <header className="mb-6 rounded-xl border border-white/8 bg-slate-900/70 backdrop-blur">
          <div className="flex items-center justify-between gap-4 px-5 py-3">
            {/* Brand + desktop nav */}
            <div className="flex items-center gap-5">
              <Link
                to="/tools"
                className="flex items-center gap-2 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                <span className="h-2 w-2 rounded-full bg-indigo-400" aria-hidden="true" />
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-indigo-400 leading-none">
                    ExportPilot
                  </p>
                  <p className="mt-0.5 text-sm font-medium text-slate-100 leading-none">
                    {organizationName}
                  </p>
                </div>
              </Link>

              <nav className="hidden gap-0.5 md:flex" aria-label="Main navigation">
                {NAV.map((item) => (
                  <Link
                    key={item.href}
                    to={item.href}
                    className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
                      pathname.startsWith(item.href)
                        ? "bg-indigo-500/15 text-indigo-300"
                        : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>

            {/* Role + sign out */}
            <div className="flex items-center gap-3">
              <span className="hidden text-xs capitalize text-slate-500 sm:block">
                {role.replaceAll("_", " ")}
              </span>
              <Button size="sm" variant="secondary" onClick={onLogout}>
                Sign out
              </Button>
            </div>
          </div>

          {/* Mobile nav — scrollable row below header bar */}
          <nav
            className="flex gap-0.5 overflow-x-auto border-t border-white/6 px-4 py-2 md:hidden"
            aria-label="Mobile navigation"
          >
            {NAV.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  pathname.startsWith(item.href)
                    ? "bg-indigo-500/15 text-indigo-300"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </header>

        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
