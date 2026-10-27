import * as React from "react";
import { cn } from "../lib/utils";
import { Button } from "./button";
import { Skeleton } from "./spinner";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  success: "border-success-border bg-success-bg text-success-fg",
  warning: "border-warning-border bg-warning-bg text-warning-fg",
  danger: "border-danger-border bg-danger-bg text-danger-fg",
  info: "border-info-border bg-info-bg text-info-fg",
  neutral: "border-line bg-surface-2 text-ink-2",
};

const TONE_LABEL: Record<Tone, string> = {
  success: "Success",
  warning: "Warning",
  danger: "Error",
  info: "Info",
  neutral: "",
};

const ICON_PATHS: Record<Tone, string> = {
  success: "M5 13l4 4L19 7",
  warning: "M12 8v5M12 17h.01M10.3 4l-8 14h19.4l-8-14a2 2 0 0 0-3.4 0z",
  danger: "M6 6l12 12M18 6L6 18",
  info: "M12 11v6M12 7h.01",
  neutral: "M6 12h12",
};

export function ToneIcon({ tone, className }: { tone: Tone; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("h-4 w-4 shrink-0", className)}
      aria-hidden="true"
    >
      <path d={ICON_PATHS[tone]} />
    </svg>
  );
}

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

/** Status is always icon + text, never color alone. */
export function Badge({ tone = "neutral", className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        TONE_CLASSES[tone],
        className
      )}
      {...props}
    >
      <ToneIcon tone={tone} className="h-3 w-3" />
      {children}
    </span>
  );
}

export interface AlertProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  tone?: Exclude<Tone, "neutral">;
  title?: React.ReactNode;
}

export function Alert({ tone = "info", title, className, children, ...props }: AlertProps) {
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn("flex gap-3 rounded-panel border p-3 text-sm", TONE_CLASSES[tone], className)}
      {...props}
    >
      <ToneIcon tone={tone} className="mt-0.5" />
      <div className="min-w-0 space-y-0.5">
        <p className="font-semibold">
          <span className="sr-only">{TONE_LABEL[tone]}: </span>
          {title}
        </p>
        {children && <div className="text-ink">{children}</div>}
      </div>
    </div>
  );
}

export interface EmptyStateProps {
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-2 rounded-card border border-dashed border-line-strong bg-surface px-6 py-10 text-center",
        className
      )}
    >
      <p className="text-base font-semibold text-ink">{title}</p>
      {description && <p className="max-w-md text-sm text-ink-2">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export interface QueryStateProps {
  isLoading: boolean;
  isError: boolean;
  error?: unknown;
  onRetry?: () => void;
  isEmpty?: boolean;
  empty?: React.ReactNode;
  children: React.ReactNode;
}

export function QueryState({ isLoading, isError, error, onRetry, isEmpty, empty, children }: QueryStateProps) {
  if (isLoading) {
    return (
      <div role="status" aria-busy="true" className="space-y-3">
        <span className="sr-only">Loading</span>
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (isError) {
    const message =
      typeof error === "string" ? error : error instanceof Error ? error.message : "Something went wrong.";
    return (
      <Alert tone="danger" title="Could not load this data">
        <p>{message}</p>
        {onRetry && (
          <Button size="sm" variant="secondary" className="mt-2" onClick={onRetry}>
            Retry
          </Button>
        )}
      </Alert>
    );
  }
  if (isEmpty) {
    return <>{empty ?? <EmptyState title="Nothing here yet" />}</>;
  }
  return <>{children}</>;
}
