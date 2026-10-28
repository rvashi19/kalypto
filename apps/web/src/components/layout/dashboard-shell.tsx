import { useEffect, useRef, useState, type PropsWithChildren } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button, cn } from "@repo/ui";

const NAV_GROUPS = [
  {
    label: "Workspace",
    items: [
      { label: "Dashboard", href: "/dashboard" },
      { label: "Tools", href: "/tools" },
      { label: "Shipments", href: "/shipments" },
      { label: "Document verifier", href: "/document-verifier" },
      { label: "Document builder", href: "/documents" },
    ],
  },
  {
    label: "Lookup",
    items: [
      { label: "HSN finder", href: "/hsn" },
      { label: "Incentive finder", href: "/incentives" },
      { label: "Export quote", href: "/calculators/export-quote" },
    ],
  },
  {
    label: "Compliance",
    items: [{ label: "Country checker", href: "/compliance/checker" }],
  },
];

const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-nav";

interface SidebarProps {
  organizationName: string;
  role: string;
  onLogout: () => void;
  pathname: string;
  onNavigate?: () => void;
}

function SidebarContent({ organizationName, role, onLogout, pathname, onNavigate }: SidebarProps) {
  return (
    <div className="flex h-full flex-col bg-nav text-nav-text">
      <div className="border-b border-[#2a2d33] px-4 py-4">
        <p className="text-sm font-semibold text-[#ffffff]">KALYPTO</p>
        <p className="truncate text-xs">{organizationName}</p>
      </div>
      <nav aria-label="Main navigation" className="flex-1 space-y-5 overflow-y-auto px-2 py-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="px-3 pb-1 text-xs font-medium uppercase text-[#8b93a1]">{group.label}</p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      to={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "block rounded-control border-l-2 px-3 py-2 text-sm font-medium transition-colors hover:bg-[#1c1f24]",
                        FOCUS,
                        active ? "border-brand bg-[#23272e] text-[#ffffff]" : "border-transparent"
                      )}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="space-y-2 border-t border-[#2a2d33] p-4">
        <p className="text-xs capitalize">{role.replaceAll("_", " ")}</p>
        <Button size="sm" variant="secondary" className="w-full" onClick={onLogout}>
          Sign out
        </Button>
      </div>
    </div>
  );
}

export function DashboardShell({
  organizationName,
  role,
  onLogout,
  children,
}: PropsWithChildren<{ organizationName: string; role: string; onLogout: () => void }>) {
  const { pathname } = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!drawerOpen) return;
    const panel = drawer.current;
    panel?.querySelector<HTMLElement>("a, button")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setDrawerOpen(false);
        menuButton.current?.focus();
        return;
      }
      if (e.key !== "Tab" || !panel) return;
      const f = panel.querySelectorAll<HTMLElement>("a[href], button:not([disabled])");
      if (f.length === 0) return;
      const first = f[0];
      const last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const closeDrawer = () => setDrawerOpen(false);
  const sidebarProps = { organizationName, role, onLogout, pathname };

  return (
    <div className="atlassian-shell min-h-screen bg-canvas text-ink">
      <a
        href="#main-content"
        className="sr-only z-[60] rounded-control bg-surface px-3 py-2 text-sm font-medium text-brand focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:ring-2 focus:ring-brand"
      >
        Skip to main content
      </a>

      <aside className="fixed inset-y-0 left-0 hidden w-[232px] min-[860px]:block">
        <SidebarContent {...sidebarProps} />
      </aside>

      <header className="sticky top-0 z-40 flex items-center justify-between bg-nav px-4 py-2 min-[860px]:hidden">
        <span className="text-sm font-semibold text-[#ffffff]">KALYPTO</span>
        <button
          ref={menuButton}
          type="button"
          aria-expanded={drawerOpen}
          aria-controls="mobile-nav"
          onClick={() => setDrawerOpen(true)}
          className={cn(
            "rounded-control border border-[#3a3f47] px-3 py-1.5 text-sm font-medium text-nav-text",
            FOCUS
          )}
        >
          Menu
        </button>
      </header>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 min-[860px]:hidden">
          <div
            className="absolute inset-0 bg-[rgba(16,18,20,0.5)]"
            onClick={closeDrawer}
            aria-hidden="true"
          />
          <div
            id="mobile-nav"
            ref={drawer}
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
            className="absolute inset-y-0 left-0 w-[260px] max-w-[85%] shadow-pop"
          >
            <SidebarContent {...sidebarProps} onNavigate={closeDrawer} />
            <button
              type="button"
              onClick={() => {
                closeDrawer();
                menuButton.current?.focus();
              }}
              className={cn(
                "absolute right-2 top-3 rounded-control px-2 py-1 text-xs text-nav-text",
                FOCUS
              )}
            >
              Close
            </button>
          </div>
        </div>
      )}

      <main id="main-content" tabIndex={-1} className="min-[860px]:pl-[232px] focus:outline-none">
        <div className="mx-auto max-w-[1120px] px-4 py-6 sm:px-6">{children}</div>
      </main>
    </div>
  );
}
