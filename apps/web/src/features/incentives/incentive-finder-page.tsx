import type { IncentiveDetailResponse, IncentiveRateItem } from "@repo/shared";
import { Button } from "@repo/ui";
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

const inputClass =
  "w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm text-ink placeholder:text-ink-2 outline-none transition focus:border-warning-border focus:ring-2 focus:ring-warning-border";

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
      <section className="rounded-3xl border border-line bg-surface   px-6 py-8 text-center md:py-10">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-warning-fg">
          — Export Incentives · RoDTEP · Drawback · RoSCTL —
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink md:text-3xl">
          Incentive Finder
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-ink-2">
          Look up RoDTEP, Drawback, and RoSCTL rates for any Indian export HSN code.{" "}
          <Link to="/hsn" className="text-warning-fg hover:text-warning-fg">
            Find your HSN code first
          </Link>{" "}
          for best accuracy.
        </p>

        <div className="mx-auto mt-6 flex max-w-3xl flex-col gap-2 sm:flex-row">
          <input
            className={`${inputClass} flex-1`}
            placeholder="Enter or select HSN code (e.g. 12119030)"
            value={hsn}
            onChange={(e) => setHsn(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && hsn.trim()) searchMutation.mutate(hsn.trim());
            }}
          />
          <select
            value={scheme}
            onChange={(e) => setScheme(e.target.value)}
            className="rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm text-ink outline-none focus:border-warning-border"
          >
            <option value="all">All schemes</option>
            <option value="rodtep">RoDTEP</option>
            <option value="drawback">Drawback</option>
            <option value="rosctl">RoSCTL</option>
          </select>
          <Button
            className="shrink-0   "
            disabled={searchMutation.isPending || !hsn.trim()}
            onClick={() => searchMutation.mutate(hsn.trim())}
          >
            {searchMutation.isPending ? "Searching…" : "Find incentives"}
          </Button>
        </div>

        {hsn.trim() ? (
          <div className="mt-3">
            <Link
              to={`/calculators/export-quote?hsn_code=${encodeURIComponent(hsn.trim())}`}
              className="text-xs font-medium text-warning-fg hover:text-warning-fg"
            >
              Calculate landed cost / export quote for this HSN →
            </Link>
          </div>
        ) : null}

        {isAdmin ? (
          <label className="mt-3 inline-flex items-center gap-2 text-xs text-ink-2">
            <input
              type="checkbox"
              checked={includeUnapproved}
              onChange={(e) => {
                setIncludeUnapproved(e.target.checked);
                if (hsn.trim()) searchMutation.mutate(hsn.trim());
              }}
            />
            Admin: include pending / expired records
          </label>
        ) : null}

        {searchMutation.error instanceof Error ? (
          <p className="mt-3 text-sm text-danger-fg">{searchMutation.error.message}</p>
        ) : null}
      </section>

      {!data && !searchMutation.isPending ? (
        <div className="mt-6 rounded-2xl border border-dashed border-line bg-surface p-8 text-center text-sm text-ink-2">
          Enter an HSN code above. For best accuracy, classify or verify the HSN in HSN Finder
          first.
        </div>
      ) : null}

      {data ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_380px]">
          <section className="space-y-5">
            {data.count === 0 ? (
              <EmptyState data={data} />
            ) : (
              grouped.map(([key, items]) => (
                <div key={key}>
                  <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-warning-fg">
                    {schemeName(key)}
                    <span className="text-[10px] text-ink-2">{items.length}</span>
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
            <p className="text-[11px] leading-5 text-ink-2">{data.disclaimer}</p>
          </section>

          <aside className="lg:sticky lg:top-4 lg:self-start">
            {detailId && detailQuery.data ? (
              <DetailPanel
                detail={detailQuery.data}
                isAdmin={Boolean(isAdmin)}
                onApprove={() => approveAndRefresh(detailQuery.data.id)}
              />
            ) : (
              <div className="rounded-2xl border border-line bg-surface p-6 text-sm text-ink-2">
                Select a rate to view full details, validity period, and conditions.
              </div>
            )}
          </aside>
        </div>
      ) : null}
    </DashboardShell>
  );

  function approveAndRefresh(id: string) {
    api
      .approveIncentive(id, token!)
      .then(() => {
        if (hsn.trim()) searchMutation.mutate(hsn.trim());
      })
      .catch(() => undefined);
  }
}

function EmptyState({ data }: { data: { hsn_exists: boolean; message: string | null } }) {
  return (
    <div className="rounded-2xl border border-dashed border-warning-border bg-warning-bg p-6 text-sm leading-6 text-warning-fg">
      {data.message ??
        (data.hsn_exists
          ? "HSN exists, but no approved incentive/rate data is available for this code."
          : "Classify or verify the HSN in HSN Finder before relying on incentive rates.")}
    </div>
  );
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
      onClick={onSelect}
      className={`block w-full rounded-xl border p-4 text-left transition ${
        selected
          ? "border-warning-border bg-warning-bg ring-1 ring-warning-border"
          : "border-line bg-surface hover:border-line-strong hover:bg-surface"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-ink">{item.hsn_code}</span>
          {item.match_level === "prefix" ? (
            <span className="rounded border border-line-strong px-1.5 py-0.5 text-[10px] text-ink-2">
              applies at {item.normalized_hsn_code}
            </span>
          ) : null}
        </span>
        <span className="font-mono text-lg font-bold text-warning-fg">{formatRate(item)}</span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-ink-2 sm:grid-cols-4">
        <Field
          label="Cap"
          value={
            item.cap_value != null
              ? `${item.cap_value}${item.cap_unit ? ` ${item.cap_unit}` : ""}`
              : "—"
          }
        />
        <Field label="Unit" value={item.unit_of_quantity ?? "—"} />
        <Field label="Valid from" value={new Date(item.effective_from).toLocaleDateString()} />
        <Field
          label="Valid to"
          value={item.effective_to ? new Date(item.effective_to).toLocaleDateString() : "current"}
        />
      </div>
      {item.condition_text ? (
        <p className="mt-2 text-xs leading-5 text-ink-2">{item.condition_text}</p>
      ) : null}
    </button>
  );
}

function DetailPanel({
  detail,
  isAdmin,
  onApprove,
}: {
  detail: IncentiveDetailResponse;
  isAdmin: boolean;
  onApprove: () => void;
}) {
  return (
    <div className="space-y-4 rounded-2xl border border-line bg-surface p-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-warning-fg">
          {schemeName(detail.scheme)}
        </p>
        <p className="mt-1 font-mono text-2xl font-bold text-warning-fg">{formatRate(detail)}</p>
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
        <Button className="w-full" onClick={onApprove}>
          Approve this rate
        </Button>
      ) : null}

      <p className="text-[11px] leading-5 text-ink-2">{DISCLAIMER}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-ink-2">{title}</p>
      <div className="mt-2 space-y-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-xs uppercase tracking-wide text-ink-2">{label}</span>
      <span className="text-right text-ink">{value}</span>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="block text-[10px] uppercase tracking-wide text-ink-3">{label}</span>
      <span className="text-ink">{value}</span>
    </div>
  );
}
