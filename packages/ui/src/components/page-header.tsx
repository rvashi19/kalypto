import * as React from "react";
import { cn } from "../lib/utils";

export interface Breadcrumb {
  label: string;
  /** Rendered by `renderLink` (e.g. a react-router Link); omit for the current page. */
  href?: string;
}

export interface PageHeaderProps {
  title: React.ReactNode;
  breadcrumbs?: Breadcrumb[];
  renderLink?: (crumb: Breadcrumb, className: string) => React.ReactNode;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  breadcrumbs,
  renderLink,
  meta,
  actions,
  className,
}: PageHeaderProps) {
  const linkClass =
    "text-ink-2 hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded-sm";
  return (
    <header className={cn("mb-6 space-y-2", className)}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb">
          <ol className="flex flex-wrap items-center gap-1.5 text-xs">
            {breadcrumbs.map((c, i) => {
              const last = i === breadcrumbs.length - 1;
              return (
                <li key={`${c.label}-${i}`} className="flex items-center gap-1.5">
                  {c.href && !last ? (
                    renderLink ? (
                      renderLink(c, linkClass)
                    ) : (
                      <a href={c.href} className={linkClass}>
                        {c.label}
                      </a>
                    )
                  ) : (
                    <span aria-current={last ? "page" : undefined} className="text-ink-3">
                      {c.label}
                    </span>
                  )}
                  {!last && (
                    <span aria-hidden="true" className="text-ink-3">
                      /
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 className="text-2xl font-semibold leading-8 text-ink">{title}</h1>
          {meta && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2">
              {meta}
            </div>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}
