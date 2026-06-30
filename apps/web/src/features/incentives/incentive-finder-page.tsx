import type { IncentiveDetailResponse, IncentiveRateItem, IncentiveSourceCreate } from "@repo/shared";
import { Button } from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const SCHEME_LABEL: Record<string, string> = {
  rodtep: "RoDTEP",
  drawback: "Drawback",
  rosctl: "RoSCTL",
};
const SCHEME_ORDER = ["rodtep", "drawback", "rosctl"];

const inputClass =
  "w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-amber-400/60 focus:ring-2 focus:ring-amber-400/20";

const DISCLAIMER =
  "Incentive/rate information is source-backed but should be verified before filing export documents or claiming benefits.";

function schemeName(scheme: string) {
  return SCHEME_LABEL[scheme.toLowerCase()] ?? scheme.toUpperCase();
}

function isExpired(item: IncentiveRateItem) {
  return item.effective_to != null && new Date(item.effective_to) <= new Date();
}

function formatRate(item: IncentiveRateItem) {
  if (item.rate_type === "percentage") return `${item.rate_value}%`;
  if (item.rate_type === "fixed") return `₹${item.rate_value}${item.unit_of_quantity ? ` / ${item.unit_of_quantity}` : ""}`;
  return `${item.rate_value}`;
}

export function IncentiveFinderPage() {
  const { session, token, setSession } = useAuth();
  const [searchParams] = useSearchParams();
  const isAdmin = session?.membership.role === "owner";

  const [hsn, setHsn] = useState(searchParams.get("hsn_code") ?? "");
  const [scheme, setScheme] = useState("all");
  const [includeUnapproved, setIncludeUnapproved] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  const searchMutation = useMutation({
    mutationFn: (code: string) =>
      api.incentiveSearch(code, token!, { scheme, includeUnapproved: includeUnapproved && isAdmin }),
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

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });

  const data = searchMutation.data;
  const grouped = useMemo(() => {
    const map = new Map<string, IncentiveRateItem[]>();
    for (const item of data?.results ?? []) {
      const key = item.scheme.toLowerCase();
      map.set(key, [...(map.get(key) ?? []), item]);
    }
    return [...map.entries()].sort(
      (a, b) => (SCHEME_ORDER.indexOf(a[0]) + 99) - (SCHEME_ORDER.indexOf(b[0]) + 99)
    );
  }, [data]);

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <section className="rounded-3xl border border-slate-800 bg-gradient-to-b from-slate-900/80 to-slate-950 px-6 py-8 text-center md:py-10">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-amber-300/80">
          — Export Incentives · RoDTEP · Drawback · RoSCTL —
        </p>
        <h1 className="mt-3 font-serif text-4xl font-bold tracking-tight text-white md:text-5xl">
          Incentive Finder
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-400">
          Look up approved, tenant-verified incentive/rate records for a selected HSN code. This
          module does not classify products —{" "}
          <Link to="/hsn" className="text-amber-300 hover:text-amber-200">
            classify the product in HSN Finder
          </Link>{" "}
          first for best accuracy.
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
            className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-400/50"
          >
            <option value="all">All schemes</option>
            <option value="rodtep">RoDTEP</option>
            <option value="drawback">Drawback</option>
            <option value="rosctl">RoSCTL</option>
          </select>
          <Button
            className="shrink-0 !bg-amber-400 !text-slate-950 hover:!bg-amber-300"
            disabled={searchMutation.isPending || !hsn.trim()}
            onClick={() => searchMutation.mutate(hsn.trim())}
          >
            {searchMutation.isPending ? "Searching…" : "Find incentives"}
          </Button>
        </div>

        {isAdmin ? (
          <label className="mt-3 inline-flex items-center gap-2 text-xs text-slate-400">
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
          <p className="mt-3 text-sm text-rose-300">{searchMutation.error.message}</p>
        ) : null}
      </section>

      {!data && !searchMutation.isPending ? (
        <div className="mt-6 rounded-2xl border border-dashed border-slate-800 bg-slate-900/30 p-8 text-center text-sm text-slate-500">
          Enter an HSN code above. For best accuracy, classify or verify the HSN in HSN Finder first.
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
                  <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.18em] text-amber-300">
                    {schemeName(key)}
                    <span className="text-[10px] text-slate-500">{items.length}</span>
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
            <p className="text-[11px] leading-5 text-slate-500">{data.disclaimer}</p>
          </section>

          <aside className="lg:sticky lg:top-4 lg:self-start">
            {detailId && detailQuery.data ? (
              <DetailPanel
                detail={detailQuery.data}
                isAdmin={Boolean(isAdmin)}
                onApprove={() => approveAndRefresh(detailQuery.data.id)}
              />
            ) : (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-500">
                Select a rate to view source evidence, validity, and verification details.
              </div>
            )}
          </aside>
        </div>
      ) : null}

      {isAdmin ? <IncentiveAdminPanel token={token!} /> : null}
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

function IncentiveAdminPanel({ token }: { token: string }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<IncentiveSourceCreate>({
    source_name: "",
    scheme: "rodtep",
    source_url: "",
    source_type: "csv",
    refresh_interval_days: 3,
  });
  const [file, setFile] = useState<File | null>(null);
  const [importScheme, setImportScheme] = useState("rodtep");
  const [importSource, setImportSource] = useState("");

  const sourcesQuery = useQuery({ queryKey: ["inc-sources", token], queryFn: () => api.listIncentiveSources(token) });
  const pendingQuery = useQuery({ queryKey: ["inc-pending", token], queryFn: () => api.incentivePendingQueue(token) });
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["inc-sources"] });
    qc.invalidateQueries({ queryKey: ["inc-pending"] });
  };

  const registerMut = useMutation({ mutationFn: () => api.registerIncentiveSource(form, token), onSuccess: invalidate });
  const refreshMut = useMutation({ mutationFn: (id: string) => api.refreshIncentiveSource(id, token), onSuccess: invalidate });
  const approveMut = useMutation({ mutationFn: (id: string) => api.approveIncentive(id, token), onSuccess: invalidate });
  const rejectMut = useMutation({ mutationFn: (id: string) => api.rejectIncentive(id, token), onSuccess: invalidate });
  const anomalyMut = useMutation({ mutationFn: () => api.incentiveAnomalyCheck(token), onSuccess: invalidate });
  const importMut = useMutation({
    mutationFn: () => api.importIncentivesFile(file!, { source_name: importSource || "Official schedule", scheme: importScheme }, token),
    onSuccess: invalidate,
  });

  const sources = sourcesQuery.data ?? [];
  const pending = pendingQuery.data ?? [];

  return (
    <section className="mt-8 space-y-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
      <h2 className="font-serif text-xl font-semibold tracking-tight text-white">
        Official sources & approvals <span className="text-amber-300">· admin</span>
      </h2>
      <p className="max-w-3xl text-sm leading-6 text-slate-400">
        Register official DGFT/CBIC/MoT schedule files (URL re-fetched on a schedule, or upload
        directly). Imported rates land as <span className="text-amber-300">pending</span> and stay
        hidden from users until you approve them. GPT only flags anomalies — never sets rates.
      </p>

      {/* Register source */}
      <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Register official source</p>
        <div className="mt-3 grid gap-2 md:grid-cols-2 lg:grid-cols-3">
          <input className={inputClass} placeholder="Source name (e.g. DGFT RoDTEP Appendix 4R)" value={form.source_name} onChange={(e) => setForm({ ...form, source_name: e.target.value })} />
          <select className={inputClass} value={form.scheme ?? ""} onChange={(e) => setForm({ ...form, scheme: e.target.value })}>
            <option value="rodtep">RoDTEP</option>
            <option value="drawback">Drawback</option>
            <option value="rosctl">RoSCTL</option>
          </select>
          <select className={inputClass} value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value as IncentiveSourceCreate["source_type"] })}>
            <option value="csv">CSV</option>
            <option value="xlsx">XLSX</option>
            <option value="pdf">PDF</option>
          </select>
          <input className={`${inputClass} lg:col-span-2`} placeholder="Official file URL (https://…gov.in/…)" value={form.source_url ?? ""} onChange={(e) => setForm({ ...form, source_url: e.target.value })} />
          <input className={inputClass} type="number" placeholder="Refresh every N days" value={form.refresh_interval_days ?? ""} onChange={(e) => setForm({ ...form, refresh_interval_days: Number(e.target.value) || null })} />
        </div>
        <Button className="mt-3" disabled={registerMut.isPending || !form.source_name} onClick={() => registerMut.mutate()}>
          {registerMut.isPending ? "Saving…" : "Register source"}
        </Button>
        {registerMut.error instanceof Error ? <p className="mt-2 text-sm text-rose-300">{registerMut.error.message}</p> : null}
      </div>

      {/* Sources list */}
      <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Registered sources</p>
        <div className="mt-2 space-y-2">
          {sources.length ? sources.map((s) => (
            <div key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-800 p-3 text-xs">
              <div>
                <p className="text-slate-200">{s.source_name} <span className="text-slate-500">· {s.scheme ?? "—"} · {s.source_type}</span></p>
                <p className="text-slate-500">
                  {s.last_status} · {s.last_records} rows · {s.last_fetched_at ? `fetched ${new Date(s.last_fetched_at).toLocaleString()}` : "never fetched"}
                  {s.due_for_refresh ? <span className="ml-2 text-amber-300">due</span> : null}
                </p>
              </div>
              {s.source_url ? (
                <Button size="sm" variant="secondary" disabled={refreshMut.isPending} onClick={() => refreshMut.mutate(s.id)}>
                  {refreshMut.isPending ? "…" : "Refresh"}
                </Button>
              ) : <span className="text-slate-600">upload-only</span>}
            </div>
          )) : <p className="text-sm text-slate-500">No sources registered yet.</p>}
        </div>
        {refreshMut.data ? <p className="mt-2 text-sm text-emerald-300">{refreshMut.data.message}</p> : null}
        {refreshMut.error instanceof Error ? <p className="mt-2 text-sm text-rose-300">{refreshMut.error.message}</p> : null}
      </div>

      {/* Upload import */}
      <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Upload official file (CSV / XLSX / PDF)</p>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <input className={inputClass} placeholder="Source name" value={importSource} onChange={(e) => setImportSource(e.target.value)} />
          <select className={inputClass} value={importScheme} onChange={(e) => setImportScheme(e.target.value)}>
            <option value="rodtep">RoDTEP</option>
            <option value="drawback">Drawback</option>
            <option value="rosctl">RoSCTL</option>
          </select>
          <input className="text-xs text-slate-400" type="file" accept=".csv,.xlsx,.pdf,.json" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
        <Button className="mt-3" disabled={importMut.isPending || !file} onClick={() => importMut.mutate()}>
          {importMut.isPending ? "Importing…" : "Import as pending"}
        </Button>
        {importMut.data ? <p className="mt-2 text-sm text-emerald-300">Imported: {importMut.data.records_created} new, {importMut.data.records_updated} updated, {importMut.data.errors.length} error(s) — pending approval.</p> : null}
        {importMut.error instanceof Error ? <p className="mt-2 text-sm text-rose-300">{importMut.error.message}</p> : null}
      </div>

      {/* Pending approval queue */}
      <div className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-300">Pending approval ({pending.length})</p>
          <Button size="sm" variant="secondary" disabled={anomalyMut.isPending || !pending.length} onClick={() => anomalyMut.mutate()}>
            {anomalyMut.isPending ? "Checking…" : "AI anomaly check"}
          </Button>
        </div>
        {anomalyMut.data ? <p className="mt-1 text-xs text-slate-400">Checked {anomalyMut.data.checked}, flagged {anomalyMut.data.flagged}.</p> : null}
        {anomalyMut.error instanceof Error ? <p className="mt-1 text-xs text-amber-300">{anomalyMut.error.message}</p> : null}
        <div className="mt-2 space-y-2">
          {pending.length ? pending.map((r) => (
            <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-xs">
              <div>
                <p className="text-slate-200">
                  <span className="font-mono text-amber-300">{r.hsn_code}</span> · {schemeName(r.scheme)} · {formatRate(r)} · <span className="uppercase text-slate-400">{r.approval_status}</span>
                </p>
                <p className="text-slate-500">{r.source_name}{r.review_note ? <span className="text-amber-300"> · ⚠ {r.review_note}</span> : null}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" disabled={approveMut.isPending} onClick={() => approveMut.mutate(r.id)}>Approve</Button>
                <Button size="sm" variant="secondary" disabled={rejectMut.isPending} onClick={() => rejectMut.mutate(r.id)}>Reject</Button>
              </div>
            </div>
          )) : <p className="text-sm text-slate-500">No pending rates. Imported/refreshed rates appear here for approval.</p>}
        </div>
      </div>
    </section>
  );
}

function EmptyState({ data }: { data: { hsn_exists: boolean; message: string | null } }) {
  return (
    <div className="rounded-2xl border border-dashed border-amber-300/25 bg-amber-300/5 p-6 text-sm leading-6 text-amber-100">
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
          ? "border-amber-400/50 bg-amber-400/5 ring-1 ring-amber-400/30"
          : "border-slate-800 bg-slate-900/50 hover:border-slate-600 hover:bg-slate-900"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-slate-100">{item.hsn_code}</span>
          <ApprovalBadge item={item} />
          {item.match_level === "prefix" ? (
            <span className="rounded border border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-400">
              parent {item.normalized_hsn_code}
            </span>
          ) : null}
        </span>
        <span className="font-mono text-lg font-bold text-amber-300">{formatRate(item)}</span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-slate-400 sm:grid-cols-4">
        <Field label="Cap" value={item.cap_value != null ? `${item.cap_value}${item.cap_unit ? ` ${item.cap_unit}` : ""}` : "—"} />
        <Field label="Unit" value={item.unit_of_quantity ?? "—"} />
        <Field label="Valid from" value={new Date(item.effective_from).toLocaleDateString()} />
        <Field label="Valid to" value={item.effective_to ? new Date(item.effective_to).toLocaleDateString() : "current"} />
      </div>
      {item.condition_text ? (
        <p className="mt-2 text-xs leading-5 text-slate-500">{item.condition_text}</p>
      ) : null}
      <p className="mt-1 text-[11px] text-slate-600">Source: {item.source_name}</p>
    </button>
  );
}

function ApprovalBadge({ item }: { item: IncentiveRateItem }) {
  let label = item.approval_status;
  let cls = "border-slate-600/50 bg-slate-700/40 text-slate-300";
  if (isExpired(item)) {
    label = "expired";
    cls = "border-slate-600/50 bg-slate-700/40 text-slate-400";
  } else if (item.approval_status === "approved") {
    cls = "border-emerald-500/40 bg-emerald-500/15 text-emerald-300";
  } else if (item.approval_status === "pending") {
    cls = "border-amber-500/40 bg-amber-500/15 text-amber-300";
  } else if (item.approval_status === "rejected") {
    cls = "border-rose-500/40 bg-rose-500/15 text-rose-300";
  }
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {label}
    </span>
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
    <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div>
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-300">
            {schemeName(detail.scheme)}
          </p>
          <ApprovalBadge item={detail} />
        </div>
        <p className="mt-1 font-mono text-xl font-bold text-amber-300">{formatRate(detail)}</p>
        <p className="mt-1 text-sm text-slate-300">
          HSN {detail.hsn_code}
          {detail.product_description ? ` · ${detail.product_description}` : ""}
        </p>
      </div>

      <Section title="Rate details">
        <Row label="Rate type" value={detail.rate_type} />
        <Row label="Cap" value={detail.cap_value != null ? `${detail.cap_value} ${detail.cap_unit ?? ""}` : "—"} />
        <Row label="Unit" value={detail.unit_of_quantity ?? "—"} />
        <Row label="Valid from" value={new Date(detail.effective_from).toLocaleDateString()} />
        <Row label="Valid to" value={detail.effective_to ? new Date(detail.effective_to).toLocaleDateString() : "current"} />
        {detail.condition_text ? <Row label="Conditions" value={detail.condition_text} /> : null}
      </Section>

      <Section title="Verification">
        <Row label="Status" value={detail.approval_status} />
        <Row label="Verified by" value={detail.verified_by ?? "—"} />
        <Row label="Verified at" value={detail.verified_at ? new Date(detail.verified_at).toLocaleString() : "—"} />
      </Section>

      <Section title="Source evidence">
        <div className="space-y-2">
          {detail.source_evidence.length ? (
            detail.source_evidence.map((e, i) => (
              <div key={i} className="rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-xs leading-5 text-slate-400">
                <p className="font-medium text-slate-200">{e.source_name} · {e.evidence_type}</p>
                {e.document_title ? <p className="mt-0.5">{e.document_title}</p> : null}
                {e.document_date ? <p className="text-slate-500">{new Date(e.document_date).toLocaleDateString()}</p> : null}
                {e.source_url ? (
                  <a href={e.source_url} target="_blank" rel="noreferrer" className="mt-1 inline-block font-medium text-amber-300 hover:text-amber-200">
                    Open source ↗
                  </a>
                ) : null}
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">No evidence rows attached.</p>
          )}
        </div>
      </Section>

      {isAdmin && detail.approval_status !== "approved" ? (
        <Button className="w-full" onClick={onApprove}>
          Approve this rate
        </Button>
      ) : null}

      <p className="text-[11px] leading-5 text-slate-500">{DISCLAIMER}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{title}</p>
      <div className="mt-2 space-y-1">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-xs uppercase tracking-wide text-slate-500">{label}</span>
      <span className="text-right text-slate-200">{value}</span>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="block text-[10px] uppercase tracking-wide text-slate-600">{label}</span>
      <span className="text-slate-300">{value}</span>
    </div>
  );
}
