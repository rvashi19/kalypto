import type { HsnDetailResponse, HsnScrapeRequest, HsnSearchItem } from "@repo/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { inputCls } from "../../lib/ui";

const CONFIDENCE_STYLES: Record<string, string> = {
  High: "border-emerald-300/30 bg-emerald-300/10 text-emerald-200",
  Medium: "border-amber-300/30 bg-amber-300/10 text-amber-200",
  Low: "border-rose-300/30 bg-rose-300/10 text-rose-200",
};

const EMPTY_STATE =
  "No HSN match found in the imported HSN master data. This does not mean the HSN does not exist. Import/update official HSN master data or request verification.";

export function HsnFinderPage() {
  const { session, token, setSession } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("turmeric powder");
  const [selected, setSelected] = useState<HsnSearchItem | null>(null);
  const [detail, setDetail] = useState<HsnDetailResponse | null>(null);

  const searchMutation = useMutation({
    mutationFn: () => api.searchHsn(query, token!, { limit: 20 }),
    onSuccess: () => {
      setSelected(null);
      setDetail(null);
    },
  });

  const detailMutation = useMutation({
    mutationFn: (code: string) => api.getHsnDetail(code, token!),
    onSuccess: (data) => setDetail(data),
  });

  const verifyMutation = useMutation({
    mutationFn: (item: HsnSearchItem) =>
      api.createHsnVerification(
        {
          product_description: query,
          selected_hsn_code: item.normalized_code,
          alternative_hsn_codes: (searchMutation.data?.results ?? [])
            .filter((r) => r.normalized_code !== item.normalized_code)
            .slice(0, 5)
            .map((r) => r.normalized_code),
          user_notes: `Match reason: ${item.match_reason}. Flags: ${item.warning_flags.join(", ") || "none"}.`,
        },
        token!
      ),
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });

  function onSelect(item: HsnSearchItem) {
    setSelected(item);
    detailMutation.mutate(item.normalized_code);
  }

  const results = searchMutation.data?.results ?? [];
  const isAdmin = session?.membership.role === "owner";

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <Card className="mb-5 overflow-hidden border-white/10 bg-slate-900/80">
        <div className="h-px bg-gradient-to-r from-transparent via-cyan-200/50 to-transparent" />
        <CardHeader>
          <CardTitle className="text-2xl tracking-[-0.02em]">HSN Finder</CardTitle>
          <CardDescription>
            Classify products against imported official HSN/ITC(HS) master data. This is
            classification only — incentives and rates are handled separately by the Incentive
            Finder.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
            <label className="block space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">
                Product or HSN code
              </span>
              <input
                className={inputCls}
                placeholder="Enter product name or HSN code"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && query.trim()) searchMutation.mutate();
                }}
              />
            </label>
            <Button disabled={searchMutation.isPending || !query.trim()} onClick={() => searchMutation.mutate()}>
              {searchMutation.isPending ? "Searching..." : "Search HSN"}
            </Button>
          </div>
          {searchMutation.error instanceof Error ? (
            <p className="mt-3 text-sm text-rose-300">{searchMutation.error.message}</p>
          ) : null}
          {searchMutation.data ? (
            <p className="mt-3 text-xs leading-5 text-amber-300">{searchMutation.data.disclaimer}</p>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[1fr_400px]">
        <section className="space-y-3">
          {searchMutation.data && results.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-amber-300/25 bg-amber-300/5 p-6 text-sm leading-6 text-amber-100">
              {EMPTY_STATE}
            </div>
          ) : null}

          {results.map((item) => (
            <button
              key={`${item.normalized_code}-${item.match_reason}`}
              onClick={() => onSelect(item)}
              className={`block w-full rounded-2xl border p-4 text-left transition ${
                selected?.normalized_code === item.normalized_code
                  ? "border-cyan-300/40 bg-cyan-300/10"
                  : "border-white/10 bg-slate-900/65 hover:border-white/20"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-lg font-bold text-slate-100">{item.code}</span>
                <span
                  className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] ${
                    CONFIDENCE_STYLES[item.confidence_label]
                  }`}
                >
                  {item.confidence_label} · {item.confidence_score}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-300">{item.description}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span>{item.digit_level}-digit</span>
                <span>·</span>
                <span>{item.match_reason}</span>
                {item.source_evidence.length ? (
                  <>
                    <span>·</span>
                    <span className="text-emerald-300">{item.source_evidence.length} source(s)</span>
                  </>
                ) : null}
              </div>
              {item.warning_flags.length ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {item.warning_flags.map((flag) => (
                    <span
                      key={flag}
                      className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-0.5 text-[10px] text-amber-200"
                    >
                      {flag}
                    </span>
                  ))}
                </div>
              ) : null}
              {item.verification_recommended ? (
                <p className="mt-2 text-[11px] font-semibold text-amber-300">
                  Verification recommended before filing.
                </p>
              ) : null}
            </button>
          ))}
        </section>

        <aside>
          {selected && detail ? (
            <DetailPanel
              detail={detail}
              onVerify={() => verifyMutation.mutate(selected)}
              verifyPending={verifyMutation.isPending}
              verified={Boolean(verifyMutation.data)}
              onUseForIncentives={() =>
                navigate(`/tools?hsn=${encodeURIComponent(detail.normalized_code)}`)
              }
            />
          ) : (
            <div className="rounded-2xl border border-white/10 bg-slate-900/65 p-6 text-sm text-slate-500">
              Select a result to view hierarchy, official source evidence, and policy notes.
            </div>
          )}
        </aside>
      </div>

      {isAdmin ? <AdminDataPanel token={token!} /> : null}
    </DashboardShell>
  );
}

function AdminDataPanel({ token }: { token: string }) {
  const queryClient = useQueryClient();
  const [source, setSource] = useState<"ogd" | "file">("ogd");
  const [sourceVersion, setSourceVersion] = useState("itchs-2024");
  const [resourceId, setResourceId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [fileUrl, setFileUrl] = useState("");

  const jobsQuery = useQuery({
    queryKey: ["hsn-import-jobs", token],
    queryFn: () => api.listHsnImportJobs(token),
  });

  const scrapeMutation = useMutation({
    mutationFn: () => {
      const payload: HsnScrapeRequest =
        source === "ogd"
          ? { source, source_version: sourceVersion, resource_id: resourceId, api_key: apiKey || null }
          : { source, source_version: sourceVersion, url: fileUrl };
      return api.scrapeHsn(payload, token);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["hsn-import-jobs"] }),
  });

  const jobs = jobsQuery.data ?? [];

  return (
    <Card className="mt-5 overflow-hidden border-amber-300/20 bg-slate-900/80">
      <CardHeader>
        <CardTitle className="text-lg tracking-[-0.02em]">Official HSN data (admin)</CardTitle>
        <CardDescription>
          Refresh the HSN master from an official source. data.gov.in needs a free api.data.gov.in
          key + dataset resource id; the file mode imports a published CSV/XLSX/JSON snapshot from a
          government domain. Runs are rate-limited and source-versioned.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          {(["ogd", "file"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setSource(mode)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-semibold uppercase tracking-wide ${
                source === mode
                  ? "border-cyan-300/40 bg-cyan-300/10 text-cyan-200"
                  : "border-white/10 text-slate-400"
              }`}
            >
              {mode === "ogd" ? "data.gov.in API" : "Official file URL"}
            </button>
          ))}
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <AdminField label="Source version">
            <input className={inputCls} value={sourceVersion} onChange={(e) => setSourceVersion(e.target.value)} />
          </AdminField>
          {source === "ogd" ? (
            <>
              <AdminField label="Resource id (data.gov.in)">
                <input className={inputCls} value={resourceId} onChange={(e) => setResourceId(e.target.value)} placeholder="e.g. 35985678-0d79-..." />
              </AdminField>
              <AdminField label="API key (optional if set on server)">
                <input className={inputCls} value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="api.data.gov.in key" />
              </AdminField>
            </>
          ) : (
            <AdminField label="Official file URL">
              <input className={inputCls} value={fileUrl} onChange={(e) => setFileUrl(e.target.value)} placeholder="https://<gov-domain>/itc-hs.csv" />
            </AdminField>
          )}
        </div>

        <Button
          disabled={scrapeMutation.isPending || (source === "ogd" ? !resourceId : !fileUrl) || !sourceVersion}
          onClick={() => scrapeMutation.mutate()}
        >
          {scrapeMutation.isPending ? "Fetching..." : "Fetch & import official data"}
        </Button>

        {scrapeMutation.error instanceof Error ? (
          <p className="text-sm text-rose-300">{scrapeMutation.error.message}</p>
        ) : null}
        {scrapeMutation.data ? (
          <p className="text-sm text-emerald-300">
            {scrapeMutation.data.status}: {scrapeMutation.data.records_created} created,{" "}
            {scrapeMutation.data.records_updated} updated, {scrapeMutation.data.errors.length} error(s).
          </p>
        ) : null}

        <div className="rounded-xl border border-white/8 bg-slate-950/60 p-4">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">Recent import jobs</p>
          <div className="mt-2 space-y-1.5 text-xs">
            {jobs.length ? (
              jobs.slice(0, 6).map((job) => (
                <div key={job.id} className="flex flex-wrap justify-between gap-2 text-slate-400">
                  <span className="text-slate-300">{job.source_name}</span>
                  <span>
                    {job.import_type} · {job.status} · +{job.records_created}/~{job.records_updated} ·{" "}
                    {new Date(job.created_at).toLocaleString()}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-slate-500">No import jobs yet.</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function AdminField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function DetailPanel({
  detail,
  onVerify,
  verifyPending,
  verified,
  onUseForIncentives,
}: {
  detail: HsnDetailResponse;
  onVerify: () => void;
  verifyPending: boolean;
  verified: boolean;
  onUseForIncentives: () => void;
}) {
  return (
    <div className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/80 p-5">
      <div>
        <p className="font-mono text-2xl font-bold text-slate-100">{detail.code}</p>
        <p className="mt-1 text-sm leading-6 text-slate-300">{detail.description}</p>
      </div>

      <div className="rounded-xl border border-white/8 bg-slate-950/60 p-4">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">Hierarchy</p>
        <div className="mt-2 space-y-1 text-sm text-slate-300">
          <HierRow label="Chapter" value={detail.hierarchy.chapter_code} extra={detail.chapter_name} />
          <HierRow label="Heading" value={detail.hierarchy.heading_code} />
          <HierRow label="Subheading" value={detail.hierarchy.subheading_code} />
          <HierRow label="Tariff line" value={detail.digit_level === 8 ? detail.normalized_code : null} />
        </div>
      </div>

      {detail.import_policy || detail.export_policy || detail.policy_condition ? (
        <div className="rounded-xl border border-white/8 bg-slate-950/60 p-4 text-sm text-slate-300">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">Policy notes</p>
          {detail.import_policy ? <p className="mt-2">Import: {detail.import_policy}</p> : null}
          {detail.export_policy ? <p className="mt-1">Export: {detail.export_policy}</p> : null}
          {detail.policy_condition ? (
            <p className="mt-1 text-slate-400">{detail.policy_condition}</p>
          ) : null}
        </div>
      ) : null}

      <div className="rounded-xl border border-white/8 bg-slate-950/60 p-4">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
          Official source evidence
        </p>
        <div className="mt-2 space-y-2">
          {detail.source_evidence.length ? (
            detail.source_evidence.map((evidence, index) => (
              <div key={index} className="rounded-lg bg-white/[0.03] p-3 text-xs leading-5 text-slate-400">
                <p className="font-semibold text-slate-200">
                  {evidence.source_name} · {evidence.evidence_type}
                </p>
                {evidence.document_title ? <p className="mt-1">{evidence.document_title}</p> : null}
                {evidence.source_url ? (
                  <a
                    href={evidence.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 inline-block font-semibold text-cyan-200 hover:text-cyan-100"
                  >
                    Open source
                  </a>
                ) : null}
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">No evidence rows attached.</p>
          )}
        </div>
        <p className="mt-2 text-[11px] text-slate-500">
          Source: {detail.source_name}
          {detail.source_version ? ` · version ${detail.source_version}` : ""}
        </p>
      </div>

      <div className="space-y-2">
        <Button className="w-full" variant="secondary" disabled={verifyPending || verified} onClick={onVerify}>
          {verified ? "Verification requested" : verifyPending ? "Submitting..." : "Verify with CHA/customs broker"}
        </Button>
        <Button className="w-full" onClick={onUseForIncentives}>
          Use this HSN for Incentive Finder
        </Button>
        {!detail.incentive_rate_available ? (
          <p className="text-[11px] leading-5 text-slate-500">
            HSN exists, but no approved incentive/rate data is available for this code yet.
          </p>
        ) : null}
      </div>

      <p className="text-[11px] leading-5 text-amber-300">{detail.disclaimer}</p>
    </div>
  );
}

function HierRow({ label, value, extra }: { label: string; value: string | null; extra?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-xs uppercase tracking-wide text-slate-500">{label}</span>
      <span className="font-mono text-slate-200">
        {value}
        {extra ? <span className="ml-2 font-sans text-xs text-slate-500">{extra}</span> : null}
      </span>
    </div>
  );
}
