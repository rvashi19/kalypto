import type { HsnDetailResponse, HsnSearchItem } from "@repo/shared";
import { Button } from "@repo/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const CONFIDENCE_STYLES: Record<string, string> = {
  High: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  Medium: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  Low: "border-slate-600/50 bg-slate-700/40 text-slate-300",
};

const CHIP_GROUPS: { label: string; chips: string[] }[] = [
  { label: "Agri & Food", chips: ["Basmati rice", "Wheat", "Maize", "Turmeric", "Cumin", "Cardamom", "Tea", "Coffee", "Sugar", "Soybean"] },
  { label: "Nuts & Fruit", chips: ["Almond", "Cashew", "Walnut", "Raisins", "Mango", "Banana", "Grapes", "Pomegranate"] },
  { label: "Pulses", chips: ["Chana", "Lentil", "Tur dal", "Moong", "Urad", "Rajma"] },
  { label: "Marine & Dairy", chips: ["Shrimp", "Fish", "Ghee", "Milk powder", "Paneer", "Honey", "Buffalo meat"] },
  { label: "Gems & Metals", chips: ["Gold", "Silver", "Diamond", "Gold jewellery", "Steel", "Aluminium", "Copper"] },
  { label: "Energy & Chem", chips: ["Diesel", "Petrol", "Crude oil", "LPG", "Urea", "DAP fertilizer", "Medicine"] },
  { label: "Electronics", chips: ["Mobile phone", "Laptop", "LED TV", "Air conditioner", "Refrigerator", "Solar panel", "Battery"] },
  { label: "Vehicles & Machinery", chips: ["Car", "Motorcycle", "Tractor", "Auto parts", "Water pump", "Electric motor"] },
  { label: "Textiles & More", chips: ["Cotton shirt", "T-shirt", "Jeans", "Saree", "Leather wallet", "Leather shoes", "Wooden furniture", "Ceramic tiles"] },
];

const LEVELS = [
  { label: "All", value: 0 },
  { label: "Chapter · 2", value: 2 },
  { label: "Heading · 4", value: 4 },
  { label: "Sub-heading · 6", value: 6 },
  { label: "Tariff item · 8", value: 8 },
] as const;

type SortKey = "relevance" | "code_asc" | "code_desc" | "az";

const EMPTY_STATE =
  "No HSN match found in the imported master data. This does not mean the code does not exist — try the AI verify, or import/update the official HSN master.";

const inputClass =
  "w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-amber-400/60 focus:ring-2 focus:ring-amber-400/20";

export function HsnFinderPage() {
  const { session, token, setSession } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState(0);
  const [sort, setSort] = useState<SortKey>("relevance");
  const [selected, setSelected] = useState<HsnSearchItem | null>(null);
  const [detail, setDetail] = useState<HsnDetailResponse | null>(null);
  const [browse, setBrowse] = useState(false);
  const [chipGroup, setChipGroup] = useState(0);

  const statsQuery = useQuery({
    queryKey: ["hsn-stats", token],
    queryFn: () => api.hsnStats(token!),
    enabled: Boolean(token),
  });

  const chaptersQuery = useQuery({
    queryKey: ["hsn-chapters", token],
    queryFn: () => api.hsnChapters(token!),
    enabled: Boolean(token && browse),
  });

  const searchMutation = useMutation({
    mutationFn: (vars: { q: string; level: number }) =>
      api.searchHsn(vars.q, token!, { limit: 30, digitLevel: vars.level || undefined }),
    onSuccess: () => {
      setSelected(null);
      setDetail(null);
    },
  });

  const detailMutation = useMutation({
    mutationFn: (code: string) => api.getHsnDetail(code, token!),
    onSuccess: (data) => setDetail(data),
  });

  const aiMutation = useMutation({ mutationFn: () => api.classifyHsnAi(query, token!) });

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

  function runSearch(q: string, lvl = level) {
    if (!q.trim()) return;
    setBrowse(false);
    setQuery(q);
    searchMutation.mutate({ q, level: lvl });
  }

  function onSelect(item: HsnSearchItem) {
    setSelected(item);
    detailMutation.mutate(item.normalized_code);
  }

  const results = useMemo(() => {
    const list = [...(searchMutation.data?.results ?? [])];
    if (sort === "code_asc") list.sort((a, b) => a.normalized_code.localeCompare(b.normalized_code));
    if (sort === "code_desc") list.sort((a, b) => b.normalized_code.localeCompare(a.normalized_code));
    if (sort === "az") list.sort((a, b) => a.description.localeCompare(b.description));
    return list;
  }, [searchMutation.data, sort]);

  const hasSearched = Boolean(searchMutation.data) || searchMutation.isPending;
  const stats = statsQuery.data;

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      {/* Hero — styled after hsn.codes */}
      <section className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-b from-slate-900/80 to-slate-950 px-6 py-10 text-center md:py-14">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-amber-300/80">
          — Harmonised System of Nomenclature · India ITC-HS —
        </p>
        <h1 className="mt-4 font-serif text-4xl font-bold tracking-tight text-white md:text-6xl">
          HSN Code Finder
        </h1>
        <p className="mt-1 font-serif text-3xl italic text-amber-300 md:text-5xl">
          Verified India Database
        </p>
        <p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-slate-400">
          Search India&apos;s complete ITC-HS classification by product name or HSN code.
          Over 14,000 codes across all 98 chapters — from 2-digit chapters to 8-digit tariff lines.
        </p>

        {/* Stats */}
        <div className="mx-auto mt-8 grid max-w-3xl grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat value={stats?.total_codes} label="HSN codes" />
          <Stat value={stats?.chapters} label="Chapters" />
          <Stat value={stats?.tariff_items} label="8-digit items" />
          <Stat value={stats?.verified_mappings} label="Verified maps" />
        </div>

        {/* Search */}
        <div className="mx-auto mt-8 max-w-3xl">
          <div className="flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900/90 p-2 shadow-lg focus-within:border-amber-400/50 focus-within:ring-2 focus-within:ring-amber-400/15">
            <span className="pl-2 text-slate-500">
              <SearchIcon />
            </span>
            <input
              autoFocus
              className="flex-1 bg-transparent px-1 py-2 text-sm text-slate-100 placeholder:text-slate-500 outline-none"
              placeholder="Search by HSN code (e.g. 8517) or product name (e.g. rice, mobile phone)…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") runSearch(query);
              }}
            />
            <Button
              className="shrink-0 !bg-amber-400 !text-slate-950 hover:!bg-amber-300"
              disabled={searchMutation.isPending || !query.trim()}
              onClick={() => runSearch(query)}
            >
              {searchMutation.isPending ? "Searching…" : "Search"}
            </Button>
            <Button
              variant="secondary"
              className="shrink-0"
              disabled={aiMutation.isPending || !query.trim()}
              onClick={() => aiMutation.mutate()}
            >
              {aiMutation.isPending ? "Verifying…" : "AI verify"}
            </Button>
          </div>

          {/* Quick chips — grouped by category */}
          <div className="mt-4 flex flex-wrap justify-center gap-1.5">
            {CHIP_GROUPS.map((group, i) => (
              <button
                key={group.label}
                onClick={() => setChipGroup(i)}
                className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition ${
                  chipGroup === i
                    ? "bg-amber-400/15 text-amber-200"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {group.label}
              </button>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap justify-center gap-2">
            {CHIP_GROUPS[chipGroup].chips.map((chip) => (
              <button
                key={chip}
                onClick={() => runSearch(chip)}
                className="rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1 text-xs text-slate-400 transition hover:border-amber-400/40 hover:text-amber-200"
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        {searchMutation.error instanceof Error ? (
          <p className="mt-3 text-sm text-rose-300">{searchMutation.error.message}</p>
        ) : null}
        {aiMutation.error instanceof Error ? (
          <p className="mt-3 text-sm text-amber-300">AI verification unavailable: {aiMutation.error.message}</p>
        ) : null}
        {aiMutation.data ? <AiVerdict data={aiMutation.data} /> : null}
      </section>

      {/* Filter tabs + sort */}
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex flex-wrap gap-1">
          <button
            onClick={() => setBrowse((b) => !b)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              browse
                ? "bg-amber-400/15 text-amber-200"
                : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
            }`}
          >
            Browse Chapters
          </button>
          <span className="mx-1 self-center text-slate-700">|</span>
          {LEVELS.map((l) => (
            <button
              key={l.value}
              onClick={() => {
                setLevel(l.value);
                if (query.trim()) runSearch(query, l.value);
              }}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                level === l.value && !browse
                  ? "bg-amber-400/15 text-amber-200"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          {searchMutation.data ? <span>{results.length} results</span> : null}
          <span>Sort</span>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200 outline-none focus:border-amber-400/50"
          >
            <option value="relevance">Relevance</option>
            <option value="code_asc">Code ↑</option>
            <option value="code_desc">Code ↓</option>
            <option value="az">A → Z</option>
          </select>
        </div>
      </div>

      {/* Browse chapters */}
      {browse ? (
        <div className="mt-5">
          {chaptersQuery.isPending ? (
            <p className="text-sm text-slate-500">Loading chapters…</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {(chaptersQuery.data ?? []).map((ch) => (
                <button
                  key={ch.code}
                  onClick={() => runSearch(ch.code)}
                  className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 text-left transition hover:border-amber-400/40 hover:bg-slate-900"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-bold text-amber-300">Ch {ch.code}</span>
                    <span className="text-[10px] text-slate-500">{ch.count} codes</span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-300">{ch.name}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : null}

      {/* Results + detail */}
      <div className={`mt-5 grid gap-6 lg:grid-cols-[1fr_400px] ${browse ? "hidden" : ""}`}>
        <section className="space-y-3">
          {searchMutation.isPending ? (
            <>
              <ResultSkeleton />
              <ResultSkeleton />
              <ResultSkeleton />
            </>
          ) : null}

          {searchMutation.data && results.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center text-sm leading-6 text-slate-400">
              {EMPTY_STATE}
            </div>
          ) : null}

          {!hasSearched ? (
            <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/30 p-10 text-center text-sm text-slate-500">
              Search above to find HSN codes — by product (“basmati rice”) or code (“0910”).
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
                navigate(`/incentives?hsn_code=${encodeURIComponent(detail.normalized_code)}`)
              }
              onUseForExportQuote={() =>
                navigate(`/calculators/export-quote?hsn_code=${encodeURIComponent(detail.normalized_code)}`)
              }
            />
          ) : (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-500">
              Select a result to view its hierarchy, code details, and policy notes.
            </div>
          )}
        </aside>
      </div>

    </DashboardShell>
  );
}

function Stat({ value, label }: { value: number | undefined; label: string }) {
  return (
    <div>
      <p className="font-mono text-2xl font-bold text-amber-300 md:text-3xl">
        {value == null ? "—" : value.toLocaleString("en-IN")}
      </p>
      <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
    </div>
  );
}

function AiVerdict({ data }: { data: import("@repo/shared").HsnAiClassifyResponse }) {
  return (
    <div className="mx-auto mt-4 max-w-3xl rounded-xl border border-amber-400/25 bg-amber-400/5 p-3 text-left text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-amber-200">AI Classification:</span>
        <span className="font-mono text-slate-100">{data.hsn_code ?? "—"}</span>
        <VerificationChip status={data.verification} />
      </div>
      {data.description ? <p className="mt-1 text-slate-300">{data.description}</p> : null}
      {data.reasoning ? <p className="mt-1 text-xs text-slate-400">{data.reasoning}</p> : null}
    </div>
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
          ? "border-amber-400/50 bg-amber-400/5 ring-1 ring-amber-400/30"
          : "border-slate-800 bg-slate-900/50 hover:border-slate-600 hover:bg-slate-900"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className="font-mono text-lg font-bold tracking-wide text-amber-300">
            {item.code}
          </span>
          {item.verified ? (
            <span className="rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-300">
              ✓ Verified
            </span>
          ) : null}
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
  onUseForExportQuote,
}: {
  detail: HsnDetailResponse;
  onVerify: () => void;
  verifyPending: boolean;
  verified: boolean;
  onUseForIncentives: () => void;
  onUseForExportQuote: () => void;
}) {
  return (
    <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div>
        <div className="flex items-center gap-2">
          <p className="font-mono text-xl font-bold text-amber-300">{detail.code}</p>
          <CopyButton value={detail.code} />
        </div>
        <p className="mt-1.5 text-sm leading-6 text-slate-300">{detail.description}</p>
      </div>

      <Section title="Hierarchy">
        <div className="space-y-1 text-sm text-slate-300">
          <HierRow label="Chapter" value={detail.hierarchy.chapter_code} extra={detail.chapter_name} />
          <HierRow label="Heading" value={detail.hierarchy.heading_code} />
          <HierRow label="Sub-heading" value={detail.hierarchy.subheading_code} />
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

      <div className="space-y-2 border-t border-slate-800 pt-4">
        <Button className="w-full" variant="secondary" disabled={verifyPending || verified} onClick={onVerify}>
          {verified ? "✓ Verification requested" : verifyPending ? "Submitting…" : "Verify with CHA / customs broker"}
        </Button>
        <Button
          className="w-full !bg-amber-400 !text-slate-950 hover:!bg-amber-300"
          onClick={onUseForIncentives}
        >
          Use this HSN for Incentive Finder
        </Button>
        <Button className="w-full" variant="secondary" onClick={onUseForExportQuote}>
          Use in Export Quote calculator
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

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{title}</p>
      <div className="mt-2">{children}</div>
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
      className="rounded border border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-400 transition hover:border-amber-400/50 hover:text-amber-200"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function VerificationChip({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    cross_verified: { label: "✓ Cross-verified", cls: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300" },
    exists_weak_match: { label: "Code exists · weak match", cls: "border-amber-500/40 bg-amber-500/15 text-amber-300" },
    unverified: { label: "⚠ Unverified by source", cls: "border-rose-500/40 bg-rose-500/15 text-rose-300" },
  };
  const v = map[status] ?? map.unverified;
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${v.cls}`}>
      {v.label}
    </span>
  );
}

function SearchIcon() {
  return (
    <svg
      className="h-5 w-5"
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
