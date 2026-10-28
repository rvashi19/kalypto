import type { ReactNode } from "react";
import { Alert, Card, CardContent, CardHeader } from "@repo/ui";

export function PanelFrame({
  title,
  description,
  badge,
  children,
}: {
  title: string;
  description: string;
  badge?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          {badge}
        </div>
        <p className="text-sm text-ink-2">{description}</p>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <p className="text-xs font-medium text-ink-2">{label}</p>
      <p className="mt-2 text-xl font-semibold tabular-nums text-ink">{value}</p>
    </div>
  );
}

export function ResultColumns({ groups }: { groups: Array<[string, string[]]> }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {groups.map(([title, values]) => (
        <div key={title} className="rounded-card border border-line bg-surface p-4">
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          <div className="mt-3 space-y-2">
            {values.length ? (
              values.map((value, index) => (
                <p
                  key={`${title}-${index}`}
                  className="rounded-panel border border-line bg-surface-2 p-3 text-sm text-ink"
                >
                  {value}
                </p>
              ))
            ) : (
              <p className="text-sm text-ink-2">No items returned.</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ErrorBox({ title, message }: { title: string; message: string }) {
  return (
    <Alert tone="danger" title={title} className="mt-4">
      {message}
    </Alert>
  );
}
