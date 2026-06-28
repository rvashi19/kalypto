import type { HsnDetailResponse, HsnScrapeRequest, HsnSearchItem } from "@repo/shared";
import { Button } from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const CONFIDENCE_STYLES: Record<string, string> = {
  High: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  Medium: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  Low: "border-slate-600/50 bg-slate-700/40 text-slate-300",
};

const EMPTY_STATE =
  "No HSN match found in the imported HSN master data. This does not mean the HSN does not exist. Import/update official HSN master data or request verification.";

const inputClass =
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30";

export function HsnFinderPage() {
  const { session, token, setSession } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("turmeric powder");
  const [selected, setSelected] = useState<HsnSearchItem | null>(null);
  const [detail, setDetail] = useState<HsnDetailResponse | null>(null);

  const searchMutation = useMutation({
    mutationFn: () => api.searchHsn(query, token!, { limit: 25 }),
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
  const hasSearched = Boolean(searchMutation.data) || searchMutation.isPending;

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      {/* Search header */}
      <section className="mb-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-white">HSN Finder</h1>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-400">
              Classify products against the imported official HSN/ITC(HS) master. Classification
              only — incentives and rates are handled separately in the Incentive Finder.
            </p>
          </div>
          {searchMutation.data ? (
            <span className="rounded-full border border-slate-700 bg-slate-800/60 px-3 py-1 text-xs text-slate-400">
              {searchMutation.data.count} result{searchMutation.data.count === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <SearchIcon />
            <input
              autoFocus
              className={`${inputClass} pl-10 pr-9`}
              placeholder="Enter product name or HSN code"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && query.trim()) searchMutation.mutate();
              }}
            />
            {query ? (
              <button
                onClick={() => setQuery("")}
                aria-label="Clear"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 transition hover:text-slate-300"
              >
                ✕
              </button>
            ) : null}
          </div>
          <Button
            className="shrink-0 sm:w-36"
            disabled={searchMutation.isPending || !query.trim()}
            onClick={() => searchMutation.mutate()}
          >
            {searchMutation.isPending ? "Searching…" : "Search"}
          </Button>
        </div>
        {searchMutation.error instanceof Error ? (
          <p className="mt-3 text-sm text-rose-300">{searchMutation.error.message}</p>
        ) : null}
      </section>

      <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
        {/* Results */}
        <section className="space-y-3">
          {searchMutation.isPending ? (
            <>
              <ResultSkeleton />
              <ResultSkeleton />
              <ResultSkeleton />
            </>
          ) : null}

          {searchMutation.data && results.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center">
              <p className="text-sm leading-6 text-slate-400">{EMPTY_STATE}</p>
            </div>
          ) : null}

          {!hasSearched ? (
            <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/30 p-10 text-center text-sm text-slate-500">
              Search by product (e.g. “basmati rice”, “cotton shirt”) or an HSN code (e.g. “0910”).
            </div>
          ) : null}

          {results.map((item) => (
            <ResultCard
              key={`${item.normalized_code}-${item.match_reason}`}
              item={item}
              selected={selected?.normalized_code === item.normalized_code}
              onSelect={() => onSelect(item)}
            />
          ))}
        </section>

        {/* Detail */}
        <aside className="lg:sticky lg:top-4 lg:self-start">
          {detailMutation.isPending ? (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
              <div className="h-6 w-32 animate-pulse rounded bg-slate-800" />
              <div className="mt-3 h-4 w-full animate-pulse rounded bg-slate-800" />
              <div className="mt-2 h-4 w-2/3 animate-pulse rounded bg-slate-800" />
            </div>
          ) : selected && detail ? (
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
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-500">
              Select a result to view its hierarchy, official source evidence, and policy notes.
            </div>
          )}
        </aside>
      </div>

      {isAdmin ? <AdminDataPanel token={token!} /> : null}
    </DashboardShell>
  );
}

function ResultCard({
  item,
  selected,
  onSelect,
}: {
  item: HsnSearchItem;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`block w-full rounded-xl border p-4 text-left transition ${
        selected
          ? "border-indigo-500/60 bg-indigo-500/5 ring-1 ring-indigo-500/40"
          : "border-slate-800 bg-slate-900/50 hover:border-slate-600 hover:bg-slate-900"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-base font-semibold tracking-wide text-slate-100">
          {item.code}
        </span>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${CONFIDENCE_STYLES[item.confidence_label]}`}
        >
          {item.confidence_label} · {Math.round(item.confidence_score)}
        </span>
      </div>
      <p className="mt-1.5 text-sm leading-6 text-slate-300">{item.description}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
        <Pill>{item.digit_level}-digit</Pill>
        <span>{item.match_reason}</span>
        {item.source_evidence.length ? (
          <span className="text-emerald-400/80">· {item.source_evidence.length} source(s)</span>
        ) : null}
      </div>
      {item.warning_flags.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {item.warning_flags.slice(0, 4).map((flag) => (
            <span
              key={flag}
              className="rounded-md border border-amber-500/20 bg-amber-500/5 px-2 py-0.5 text-[10px] text-amber-300/90"
            >
              {flag}
            </span>
          ))}
        </div>
      ) : null}
    </button>
  );
}

function ResultSkeleton() {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex justify-between">
        <div className="h-5 w-24 animate-pulse rounded bg-slate-800" />
        <div className="h-5 w-16 animate-pulse rounded bg-slate-800" />
      </div>
      <div className="mt-3 h-4 w-full animate-pulse rounded bg-slate-800" />
      <div className="mt-2 h-4 w-1/2 animate-pulse rounded bg-slate-800" />
    </div>
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
    <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div>
        <div className="flex items-center gap-2">
          <p className="font-mono text-xl font-semibold text-white">{detail.code}</p>
          <CopyButton value={detail.code} />
        </div>
        <p className="mt-1.5 text-sm leading-6 text-slate-300">{detail.description}</p>
      </div>

      <Section title="Hierarchy">
        <div className="space-y-1 text-sm text-slate-300">
          <HierRow label="Chapter" value={detail.hierarchy.chapter_code} extra={detail.chapter_name} />
          <HierRow label="Heading" value={detail.hierarchy.heading_code} />
          <HierRow label="Subheading" value={detail.hierarchy.subheading_code} />
          <HierRow label="Tariff line" value={detail.digit_level === 8 ? detail.normalized_code : null} />
        </div>
      </Section>

      {detail.import_policy || detail.export_policy || detail.policy_condition ? (
        <Section title="Policy notes">
          <div className="space-y-1 text-sm text-slate-300">
            {detail.import_policy ? <p>Import: {detail.import_policy}</p> : null}
            {detail.export_policy ? <p>Export: {detail.export_policy}</p> : null}
            {detail.policy_condition ? <p className="text-slate-400">{detail.policy_condition}</p> : null}
          </div>
        </Section>
      ) : null}

      <Section title="Official source evidence">
        <div className="space-y-2">
          {detail.source_evidence.length ? (
            detail.source_evidence.map((evidence, index) => (
              <div key={index} className="rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-xs leading-5 text-slate-400">
                <p className="font-medium text-slate-200">
                  {evidence.source_name} · {evidence.evidence_type}
                </p>
                {evidence.document_title ? <p className="mt-0.5">{evidence.document_title}</p> : null}
                {evidence.source_url ? (
                  <a
                    href={evidence.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 inline-block font-medium text-indigo-300 hover:text-indigo-200"
                  >
                    Open source ↗
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
      </Section>

      <div className="space-y-2 border-t border-slate-800 pt-4">
        <Button className="w-full" variant="secondary" disabled={verifyPending || verified} onClick={onVerify}>
          {verified ? "✓ Verification requested" : verifyPending ? "Submitting…" : "Verify with CHA / customs broker"}
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

      <p className="text-[11px] leading-5 text-slate-500">{detail.disclaimer}</p>
    </div>
  );
}

function AdminDataPanel({ token }: { token: string }) {
  const queryClient = useQueryClient();
  const [source, setSource] = useState<"eximguru" | "ogd" | "file">("eximguru");
  const [sourceVersion, setSourceVersion] = useState("itchs-2026");
  const [chapters, setChapters] = useState("9, 10, 85");
  const [resourceId, setResourceId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [fileUrl, setFileUrl] = useState("");

  const jobsQuery = useQuery({
    queryKey: ["hsn-import-jobs", token],
    queryFn: () => api.listHsnImportJobs(token),
  });

  const scrapeMutation = useMutation({
    mutationFn: () => {
      let payload: HsnScrapeRequest;
      if (source === "ogd") {
        payload = { source, source_version: sourceVersion, resource_id: resourceId, api_key: apiKey || null };
      } else if (source === "file") {
        payload = { source, source_version: sourceVersion, url: fileUrl };
      } else {
        payload = {
          source,
          source_version: sourceVersion,
          chapters: chapters.trim()
            ? chapters.split(",").map((c) => Number(c.trim())).filter((n) => Number.isFinite(n) && n > 0)
            : null,
        };
      }
      return api.scrapeHsn(payload, token);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["hsn-import-jobs"] }),
  });

  const jobs = jobsQuery.data ?? [];
  const sources = [
    { id: "eximguru", label: "EximGuru (ITC-HS)" },
    { id: "ogd", label: "data.gov.in API" },
    { id: "file", label: "Official file URL" },
  ] as const;

  return (
    <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
      <h2 className="text-lg font-semibold tracking-tight text-white">Official HSN data · admin</h2>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
        Refresh the HSN master from an official or aggregator source. Runs are rate-limited and
        source-versioned, and import idempotently (no duplicate rows). EximGuru is a secondary
        ITC-HS aggregator; official DGFT/CBIC and data.gov.in remain primary.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {sources.map((s) => (
          <button
            key={s.id}
            onClick={() => setSource(s.id)}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
              source === s.id
                ? "border-indigo-500/60 bg-indigo-500/10 text-indigo-200"
                : "border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-200"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <AdminField label="Source version">
          <input className={inputClass} value={sourceVersion} onChange={(e) => setSourceVersion(e.target.value)} />
        </AdminField>
        {source === "eximguru" ? (
          <AdminField label="Chapters (comma-separated, blank = all)">
            <input className={inputClass} value={chapters} onChange={(e) => setChapters(e.target.value)} placeholder="9, 10, 85" />
          </AdminField>
        ) : source === "ogd" ? (
          <>
            <AdminField label="Resource id (data.gov.in)">
              <input className={inputClass} value={resourceId} onChange={(e) => setResourceId(e.target.value)} placeholder="35985678-0d79-…" />
            </AdminField>
            <AdminField label="API key (optional if set on server)">
              <input className={inputClass} value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="api.data.gov.in key" />
            </AdminField>
          </>
        ) : (
          <AdminField label="Official file URL">
            <input className={inputClass} value={fileUrl} onChange={(e) => setFileUrl(e.target.value)} placeholder="https://<gov-domain>/itc-hs.csv" />
          </AdminField>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          disabled={
            scrapeMutation.isPending ||
            !sourceVersion ||
            (source === "ogd" && !resourceId) ||
            (source === "file" && !fileUrl)
          }
          onClick={() => scrapeMutation.mutate()}
        >
          {scrapeMutation.isPending ? "Fetching…" : "Fetch & import"}
        </Button>
        {scrapeMutation.isPending ? (
          <span className="text-xs text-slate-500">Crawling official source — this can take a moment…</span>
        ) : null}
      </div>

      {scrapeMutation.error instanceof Error ? (
        <p className="mt-3 text-sm text-rose-300">{scrapeMutation.error.message}</p>
      ) : null}
      {scrapeMutation.data ? (
        <p className="mt-3 text-sm text-emerald-300">
          {scrapeMutation.data.status}: {scrapeMutation.data.records_created} created,{" "}
          {scrapeMutation.data.records_updated} updated, {scrapeMutation.data.errors.length} error(s).
        </p>
      ) : null}

      <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Recent import jobs</p>
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
    </section>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{title}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function AdminField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">{label}</span>
      {children}
    </label>
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

function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="rounded border border-slate-700 bg-slate-800/50 px-1.5 py-0.5 text-[10px] text-slate-400">
      {children}
    </span>
  );
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard?.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      className="rounded border border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-400 transition hover:border-slate-500 hover:text-slate-200"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function SearchIcon() {
  return (
    <svg
      className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}
