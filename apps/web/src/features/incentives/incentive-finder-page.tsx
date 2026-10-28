import type { IncentiveDetailResponse, IncentiveRateItem } from "@repo/shared";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
} from "@repo/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useLogout } from "../../lib/use-logout";

const SCHEME_LABEL: Record<string, string> = {
  rodtep: "RoDTEP",
  drawback: "Drawback",
  rosctl: "RoSCTL",
};
const SCHEME_ORDER = ["rodtep", "drawback", "rosctl"];

const DISCLAIMER =
  "Incentive/rate information is source-backed but should be verified before filing export documents or claiming benefits.";

function schemeName(scheme: string) {
  return SCHEME_LABEL[scheme.toLowerCase()] ?? scheme.toUpperCase();
}

function formatRate(item: IncentiveRateItem) {
  if (item.rate_type === "percentage") return `${item.rate_value}%`;
  if (item.rate_type === "fixed")
    return `₹${item.rate_value}${item.unit_of_quantity ? ` / ${item.unit_of_quantity}` : ""}`;
  return `${item.rate_value}`;
}

export function IncentiveFinderPage() {
  const { session, token } = useAuth();
  const [searchParams] = useSearchParams();
  const isAdmin = session?.membership.role === "owner";

  const [hsn, setHsn] = useState(searchParams.get("hsn_code") ?? "");
  const [scheme, setScheme] = useState("all");
  const [includeUnapproved, setIncludeUnapproved] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);

  const searchMutation = useMutation({
    mutationFn: (code: string) =>
      api.incentiveSearch(code, token!, {
        scheme,
        includeUnapproved: includeUnapproved && isAdmin,
      }),
    onSuccess: () => setDetailId(null),
  });

  // Auto-run when arriving from HSN Finder with a code.
  useEffect(() => {
    const fromUrl = searchParams.get("hsn_code");
    if (fromUrl) {
      setHsn(fromUrl);
      searchMutation.mutate(fromUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const detailQuery = useQuery({
    queryKey: ["incentive-detail", detailId, token],
    queryFn: () => api.getIncentive(detailId!, token!),
    enabled: Boolean(detailId && token),
  });

  const logoutMutation = useLogout();

  const data = searchMutation.data;
  const grouped = useMemo(() => {
    const map = new Map<string, IncentiveRateItem[]>();
    for (const item of data?.results ?? []) {
      const key = item.scheme.toLowerCase();
      map.set(key, [...(map.get(key) ?? []), item]);
    }
    return [...map.entries()].sort(
      (a, b) => SCHEME_ORDER.indexOf(a[0]) + 99 - (SCHEME_ORDER.indexOf(b[0]) + 99)
    );
  }, [data]);

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <PageHeader
        title="Incentive finder"
        breadcrumbs={[{ label: "Lookup" }, { label: "Incentive finder" }]}
        meta={
          <span>
            Look up RoDTEP, Drawback and RoSCTL rates for any Indian export HSN code.{" "}
            <Link to="/hsn" className="text-brand hover:underline">
              Find your HSN code first
            </Link>{" "}
            for best accuracy.
          </span>
        }
      />

      <Card>
        <CardContent className="space-y-3 pt-6">
          <form
            className="flex flex-col gap-3 sm:flex-row sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              if (hsn.trim()) searchMutation.mutate(hsn.trim());
            }}
          >
            <Field label="HSN code" className="flex-1">
              <Input
                placeholder="Enter or select HSN code (e.g. 12119030)"
                value={hsn}
                onChange={(e) => setHsn(e.target.value)}
              />
            </Field>
            <Field label="Scheme">
              <Select value={scheme} onChange={(e) => setScheme(e.target.value)}>
                <option value="all">All schemes</option>
                <option value="rodtep">RoDTEP</option>
                <option value="drawback">Drawback</option>
                <option value="rosctl">RoSCTL</option>
              </Select>
            </Field>
            <Button type="submit" loading={searchMutation.isPending} disabled={!hsn.trim()}>
              Find incentives
            </Button>
          </form>

          {hsn.trim() ? (
            <Link
              to={`/calculators/export-quote?hsn_code=${encodeURIComponent(hsn.trim())}`}
              className="inline-block text-sm font-medium text-brand hover:underline"
            >
              Calculate landed cost / export quote for this HSN →
            </Link>
          ) : null}

          {isAdmin ? (
            <div className="flex items-center gap-2 text-sm text-ink">
              <input
                id="include-unapproved"
                type="checkbox"
                className="h-4 w-4 accent-brand"
                checked={includeUnapproved}
                onChange={(e) => {
                  setIncludeUnapproved(e.target.checked);
                  if (hsn.trim()) searchMutation.mutate(hsn.trim());
                }}
              />
              <label htmlFor="include-unapproved">Admin: include pending / expired records</label>
            </div>
          ) : null}

          {searchMutation.error instanceof Error ? (
            <Alert tone="danger" title="Could not search incentives">
              {searchMutation.error.message}
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      {!data && !searchMutation.isPending ? (
        <EmptyState
          className="mt-6"
          title="No search yet"
          description="Enter an HSN code above. For best accuracy, classify or verify the HSN in HSN Finder first."
        />
      ) : null}

      {data ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_380px]">
          <section className="space-y-5">
            {data.count === 0 ? (
              <Alert tone="warning" title="No incentive rates found">
                {data.message ??
                  (data.hsn_exists
                    ? "HSN exists, but no approved incentive/rate data is available for this code."
                    : "Classify or verify the HSN in HSN Finder before relying on incentive rates.")}
              </Alert>
            ) : (
              grouped.map(([key, items]) => (
                <div key={key}>
                  <h2 className="mb-2 flex items-center gap-2 text-base font-semibold text-ink">
                    {schemeName(key)}
                    <Badge>{items.length}</Badge>
                  </h2>
                  <div className="space-y-2">
                    {items.map((item) => (
                      <RateCard
                        key={item.id}
                        item={item}
                        selected={detailId === item.id}
                        onSelect={() => setDetailId(item.id)}
                      />
                    ))}
                  </div>
                </div>
              ))
            )}
            <p className="text-xs text-ink-2">{data.disclaimer}</p>
          </section>

          <aside className="space-y-3 lg:sticky lg:top-4 lg:self-start" aria-live="polite">
            {approveError ? (
              <Alert tone="danger" title="Could not approve this rate">
                {approveError}
              </Alert>
            ) : null}
            {detailId && detailQuery.isPending ? <Skeleton className="h-48 w-full" /> : null}
            {detailId && detailQuery.error instanceof Error ? (
              <Alert tone="danger" title="Could not load rate details">
                {detailQuery.error.message}
              </Alert>
            ) : null}
            {detailId && detailQuery.data ? (
              <DetailPanel
                detail={detailQuery.data}
                isAdmin={Boolean(isAdmin)}
                approving={approving}
                onApprove={() => approveAndRefresh(detailQuery.data.id)}
              />
            ) : null}
            {!detailId ? (
              <EmptyState
                title="No rate selected"
                description="Select a rate to view full details, validity period, and conditions."
              />
            ) : null}
          </aside>
        </div>
      ) : null}
    </DashboardShell>
  );

  function approveAndRefresh(id: string) {
    setApproving(true);
    setApproveError(null);
    api
      .approveIncentive(id, token!)
      .then(() => {
        if (hsn.trim()) searchMutation.mutate(hsn.trim());
      })
      .catch((err: unknown) =>
        setApproveError(err instanceof Error ? err.message : "Approval failed. Try again.")
      )
      .finally(() => setApproving(false));
  }
}

function RateCard({
  item,
  selected,
  onSelect,
}: {
  item: IncentiveRateItem;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`block w-full rounded-panel border p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
        selected
          ? "border-brand bg-brand-soft ring-1 ring-brand"
          : "border-line bg-surface hover:border-line-strong hover:bg-surface-2"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-ink">{item.hsn_code}</span>
          {item.match_level === "prefix" ? (
            <Badge>applies at {item.normalized_hsn_code}</Badge>
          ) : null}
        </span>
        <span className="font-mono text-lg font-bold text-brand">{formatRate(item)}</span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-ink-2 sm:grid-cols-4">
        <KeyValue
          label="Cap"
          value={
            item.cap_value != null
              ? `${item.cap_value}${item.cap_unit ? ` ${item.cap_unit}` : ""}`
              : "—"
          }
        />
        <KeyValue label="Unit" value={item.unit_of_quantity ?? "—"} />
        <KeyValue label="Valid from" value={new Date(item.effective_from).toLocaleDateString()} />
        <KeyValue
          label="Valid to"
          value={item.effective_to ? new Date(item.effective_to).toLocaleDateString() : "current"}
        />
      </div>
      {item.condition_text ? (
        <p className="mt-2 text-xs text-ink-2">{item.condition_text}</p>
      ) : null}
    </button>
  );
}

function DetailPanel({
  detail,
  isAdmin,
  approving,
  onApprove,
}: {
  detail: IncentiveDetailResponse;
  isAdmin: boolean;
  approving: boolean;
  onApprove: () => void;
}) {
  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div>
          <p className="text-xs font-semibold text-brand">{schemeName(detail.scheme)}</p>
          <p className="mt-1 font-mono text-2xl font-bold text-brand">{formatRate(detail)}</p>
          <p className="mt-1 text-sm text-ink">
            HSN {detail.hsn_code}
            {detail.product_description ? ` · ${detail.product_description}` : ""}
          </p>
        </div>

        <Section title="Rate details">
          <Row label="Rate type" value={detail.rate_type} />
          <Row
            label="Cap"
            value={detail.cap_value != null ? `${detail.cap_value} ${detail.cap_unit ?? ""}` : "—"}
          />
          <Row label="Unit" value={detail.unit_of_quantity ?? "—"} />
          <Row label="Valid from" value={new Date(detail.effective_from).toLocaleDateString()} />
          <Row
            label="Valid to"
            value={
              detail.effective_to ? new Date(detail.effective_to).toLocaleDateString() : "current"
            }
          />
          {detail.condition_text ? <Row label="Conditions" value={detail.condition_text} /> : null}
        </Section>

        {isAdmin && detail.approval_status !== "approved" ? (
          <Button className="w-full" loading={approving} onClick={onApprove}>
            Approve this rate
          </Button>
        ) : null}

        <p className="text-xs text-ink-2">{DISCLAIMER}</p>
      </CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-panel border border-line bg-surface p-4">
      <h3 className="text-xs font-semibold text-ink-2">{title}</h3>
      <div className="mt-2 space-y-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-xs text-ink-2">{label}</span>
      <span className="text-right text-ink">{value}</span>
    </div>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="block text-xs text-ink-3">{label}</span>
      <span className="text-ink">{value}</span>
    </div>
  );
}
