import { type PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@repo/ui";

const NAV = [
  { label: "Tools", href: "/tools" },
  { label: "HSN Finder", href: "/hsn" },
  { label: "Incentive Finder", href: "/incentives" },
  { label: "Export Quote", href: "/calculators/export-quote" },
  { label: "Document Builder", href: "/documents" },
  { label: "Shipments", href: "/shipments" },
  { label: "Compliance Checker", href: "/compliance/checker" },
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
    <div className="atlassian-shell min-h-screen">
      <header className="sticky top-0 z-40 border-b border-[#f0f1f2] bg-white/95 backdrop-blur">
        <div className="atlassian-container flex min-h-14 items-center justify-between gap-4 py-2">
          <div className="flex min-w-0 items-center gap-6">
            <Link
              to="/tools"
              className="flex min-w-0 items-center gap-3 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1868db]"
            >
              <span
                className="relative flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-sm bg-[#1868db] text-sm font-bold text-[#ffffff]"
                aria-hidden="true"
              >
                <span className="absolute -left-1 top-1 h-7 w-4 rotate-12 bg-[#fca700]" />
                <span className="absolute -right-1 bottom-0 h-6 w-5 -rotate-12 bg-[#36b37e]" />
                <span className="relative">K</span>
              </span>
              <div className="min-w-0">
                <p className="font-display text-base font-semibold text-[#101214]">KALYPTO</p>
                <p className="truncate text-xs text-[#42526e]">{organizationName}</p>
              </div>
            </Link>

            <nav className="hidden gap-1 lg:flex" aria-label="Main navigation">
              {NAV.map((item) => {
                const active = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    to={item.href}
                    className={`rounded-full px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1868db] ${
                      active
                        ? "bg-[#e9f2fe] text-[#1868db]"
                        : "text-[#101214] hover:bg-[#f0f1f2]"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            <span className="hidden rounded-full bg-[#f0f1f2] px-3 py-1 text-xs capitalize text-[#42526e] sm:block">
              {role.replaceAll("_", " ")}
            </span>
            <Button size="sm" variant="secondary" onClick={onLogout}>
              Sign out
            </Button>
          </div>
        </div>

        <nav
          className="atlassian-container flex gap-1 overflow-x-auto pb-2 lg:hidden"
          aria-label="Mobile navigation"
        >
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                  active ? "bg-[#e9f2fe] text-[#1868db]" : "text-[#42526e] hover:bg-[#f0f1f2]"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>

      <main className="atlassian-container flex-1 py-8">{children}</main>
    </div>
  );
}
