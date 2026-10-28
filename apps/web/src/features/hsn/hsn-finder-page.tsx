import type { HsnDetailResponse, HsnSearchItem } from "@repo/shared";
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
  QueryState,
  Select,
  Skeleton,
  type Tone,
} from "@repo/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useLogout } from "../../lib/use-logout";

const CONFIDENCE_TONES: Record<string, Tone> = {
  High: "success",
  Medium: "info",
  Low: "neutral",
};

const CHIP_GROUPS: { label: string; chips: string[] }[] = [
  {
    label: "Agri & Food",
    chips: [
      "Basmati rice",
      "Wheat",
      "Maize",
      "Turmeric",
      "Cumin",
      "Cardamom",
      "Tea",
      "Coffee",
      "Sugar",
      "Soybean",
    ],
  },
  {
    label: "Nuts & Fruit",
    chips: ["Almond", "Cashew", "Walnut", "Raisins", "Mango", "Banana", "Grapes", "Pomegranate"],
  },
  { label: "Pulses", chips: ["Chana", "Lentil", "Tur dal", "Moong", "Urad", "Rajma"] },
  {
    label: "Marine & Dairy",
    chips: ["Shrimp", "Fish", "Ghee", "Milk powder", "Paneer", "Honey", "Buffalo meat"],
  },
  {
    label: "Gems & Metals",
    chips: ["Gold", "Silver", "Diamond", "Gold jewellery", "Steel", "Aluminium", "Copper"],
  },
  {
    label: "Energy & Chem",
    chips: ["Diesel", "Petrol", "Crude oil", "LPG", "Urea", "DAP fertilizer", "Medicine"],
  },
  {
    label: "Electronics",
    chips: [
      "Mobile phone",
      "Laptop",
      "LED TV",
      "Air conditioner",
      "Refrigerator",
      "Solar panel",
      "Battery",
    ],
  },
  {
    label: "Vehicles & Machinery",
    chips: ["Car", "Motorcycle", "Tractor", "Auto parts", "Water pump", "Electric motor"],
  },
  {
    label: "Textiles & More",
    chips: [
      "Cotton shirt",
      "T-shirt",
      "Jeans",
      "Saree",
      "Leather wallet",
      "Leather shoes",
      "Wooden furniture",
      "Ceramic tiles",
    ],
  },
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
  "Nothing matched in the imported master data. This does not mean the code does not exist. Try AI verify, or import/update the official HSN master.";

export function HsnFinderPage() {
  const { session, token } = useAuth();
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

  const logoutMutation = useLogout();

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
    if (sort === "code_asc")
      list.sort((a, b) => a.normalized_code.localeCompare(b.normalized_code));
    if (sort === "code_desc")
      list.sort((a, b) => b.normalized_code.localeCompare(a.normalized_code));
    if (sort === "az") list.sort((a, b) => a.description.localeCompare(b.description));
    return list;
  }, [searchMutation.data, sort]);

  const hasSearched = Boolean(searchMutation.data) || searchMutation.isPending;
  const stats = statsQuery.data;

  let detailPane: ReactNode;
  if (detailMutation.isPending) {
    detailPane = (
      <Card>
        <CardContent className="space-y-3 p-6" aria-busy="true">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </CardContent>
      </Card>
    );
  } else if (selected && detail) {
    detailPane = (
      <DetailPanel
        detail={detail}
        onVerify={() => verifyMutation.mutate(selected)}
        verifyPending={verifyMutation.isPending}
        verified={Boolean(verifyMutation.data)}
        onUseForIncentives={() =>
          navigate(`/incentives?hsn_code=${encodeURIComponent(detail.normalized_code)}`)
        }
        onUseForExportQuote={() =>
          navigate(
            `/calculators/export-quote?hsn_code=${encodeURIComponent(detail.normalized_code)}`
          )
        }
      />
    );
  } else {
    detailPane = (
      <EmptyState
        title="No code selected"
        description="Select a result to view its hierarchy, code details, and policy notes."
      />
    );
  }

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <PageHeader
        title="HSN finder"
        breadcrumbs={[{ label: "Lookup" }, { label: "HSN finder" }]}
        meta={
          <span>
            Search India&apos;s ITC-HS classification by product name or HSN code, from 2-digit
            chapters to 8-digit tariff lines.
          </span>
        }
      />

      <Card>
        <CardContent className="space-y-5 p-5">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat value={stats?.total_codes} label="HSN codes" />
            <Stat value={stats?.chapters} label="Chapters" />
            <Stat value={stats?.tariff_items} label="8-digit items" />
            <Stat value={stats?.verified_mappings} label="Verified maps" />
          </dl>

          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              runSearch(query);
            }}
          >
            <Field label="Search by HSN code or product name" className="min-w-[16rem] flex-1">
              <Input
                autoFocus
                type="search"
                placeholder="e.g. 8517, rice, mobile phone"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </Field>
            <Button type="submit" loading={searchMutation.isPending} disabled={!query.trim()}>
              Search
            </Button>
            <Button
              type="button"
              variant="secondary"
              loading={aiMutation.isPending}
              disabled={!query.trim()}
              onClick={() => aiMutation.mutate()}
            >
              AI verify
            </Button>
          </form>

          <div>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Product categories">
              {CHIP_GROUPS.map((group, i) => (
                <button
                  type="button"
                  key={group.label}
                  aria-pressed={chipGroup === i}
                  onClick={() => setChipGroup(i)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
                    chipGroup === i ? "bg-brand-soft text-brand" : "text-ink-2 hover:text-ink"
                  }`}
                >
                  {group.label}
                </button>
              ))}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {CHIP_GROUPS[chipGroup].chips.map((chip) => (
                <button
                  type="button"
                  key={chip}
                  onClick={() => runSearch(chip)}
                  className="rounded-full border border-line-strong bg-surface px-3 py-1 text-xs text-ink-2 transition hover:border-brand hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>

          {searchMutation.error instanceof Error ? (
            <Alert tone="danger" title="Search failed">
              {searchMutation.error.message}
            </Alert>
          ) : null}
          {aiMutation.error instanceof Error ? (
            <Alert tone="warning" title="AI verification unavailable">
              {aiMutation.error.message}
            </Alert>
          ) : null}
          {aiMutation.data ? <AiVerdict data={aiMutation.data} /> : null}
        </CardContent>
      </Card>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-3 border-b border-line pb-3">
        <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Code level">
          <button
            type="button"
            aria-pressed={browse}
            onClick={() => setBrowse((b) => !b)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
              browse ? "bg-brand-soft text-brand" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
            }`}
          >
            Browse chapters
          </button>
          <span className="mx-1 text-ink-3" aria-hidden="true">
            |
          </span>
          {LEVELS.map((l) => (
            <button
              type="button"
              key={l.value}
              aria-pressed={level === l.value && !browse}
              onClick={() => {
                setLevel(l.value);
                if (query.trim()) runSearch(query, l.value);
              }}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
                level === l.value && !browse
                  ? "bg-brand-soft text-brand"
                  : "text-ink-2 hover:bg-surface-2 hover:text-ink"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
        <div className="flex items-end gap-3 text-xs text-ink-2">
          {searchMutation.data ? (
            <span className="pb-2 tabular-nums">{results.length} results</span>
          ) : null}
          <Field label="Sort">
            <Select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
              <option value="relevance">Relevance</option>
              <option value="code_asc">Code ascending</option>
              <option value="code_desc">Code descending</option>
              <option value="az">A to Z</option>
            </Select>
          </Field>
        </div>
      </div>

      {browse ? (
        <div className="mt-5">
          <QueryState
            isLoading={chaptersQuery.isPending}
            isError={chaptersQuery.isError}
            error={chaptersQuery.error}
            onRetry={() => chaptersQuery.refetch()}
          >
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {(chaptersQuery.data ?? []).map((ch) => (
                <button
                  type="button"
                  key={ch.code}
                  onClick={() => runSearch(ch.code)}
                  className="rounded-panel border border-line bg-surface p-3 text-left transition hover:border-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-semibold text-brand">Ch {ch.code}</span>
                    <span className="text-xs tabular-nums text-ink-2">{ch.count} codes</span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-ink">{ch.name}</p>
                </button>
              ))}
            </div>
          </QueryState>
        </div>
      ) : null}

      <div className={`mt-5 grid gap-6 lg:grid-cols-[1fr_400px] ${browse ? "hidden" : ""}`}>
        <section className="space-y-3" aria-label="Search results">
          {searchMutation.isPending ? (
            <>
              <ResultSkeleton />
              <ResultSkeleton />
              <ResultSkeleton />
            </>
          ) : null}

          {searchMutation.data && results.length === 0 ? (
            <EmptyState title="No HSN match found" description={EMPTY_STATE} />
          ) : null}

          {!hasSearched ? (
            <EmptyState
              title="Search to find HSN codes"
              description="Search by product (basmati rice) or code (0910)."
            />
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

        <aside
          className="lg:sticky lg:top-4 lg:self-start"
          aria-label="Code details"
          aria-live="polite"
        >
          {detailPane}
        </aside>
      </div>
    </DashboardShell>
  );
}

function Stat({ value, label }: { value: number | undefined; label: string }) {
  return (
    <div>
      <dd className="font-mono text-2xl font-semibold tabular-nums text-brand">
        {value == null ? "—" : value.toLocaleString("en-IN")}
      </dd>
      <dt className="mt-1 text-xs font-medium text-ink-2">{label}</dt>
    </div>
  );
}

function AiVerdict({ data }: { data: import("@repo/shared").HsnAiClassifyResponse }) {
  return (
    <div className="rounded-panel border border-brand bg-brand-soft p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-ink">AI classification:</span>
        <span className="font-mono text-ink">{data.hsn_code ?? "—"}</span>
        <VerificationChip status={data.verification} />
      </div>
      {data.description ? <p className="mt-1 text-ink">{data.description}</p> : null}
      {data.reasoning ? <p className="mt-1 text-xs text-ink-2">{data.reasoning}</p> : null}
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
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`block w-full rounded-panel border p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
        selected
          ? "border-brand bg-brand-soft ring-1 ring-brand"
          : "border-line bg-surface hover:border-line-strong"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <span className="font-mono text-lg font-semibold text-brand">{item.code}</span>
          {item.verified ? <Badge tone="success">Verified</Badge> : null}
        </span>
        <Badge tone={CONFIDENCE_TONES[item.confidence_label] ?? "neutral"}>
          {item.confidence_label} · {Math.round(item.confidence_score)}
        </Badge>
      </div>
      <p className="mt-1.5 text-sm leading-6 text-ink">{item.description}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-2">
        <Pill>{item.digit_level}-digit</Pill>
        <span>{item.match_reason}</span>
      </div>
      {item.warning_flags.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {item.warning_flags.slice(0, 4).map((flag) => (
            <Badge key={flag} tone="warning">
              {flag}
            </Badge>
          ))}
        </div>
      ) : null}
    </button>
  );
}

function ResultSkeleton() {
  return (
    <div className="space-y-3 rounded-panel border border-line bg-surface p-4" aria-hidden="true">
      <div className="flex justify-between">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-5 w-16" />
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-1/2" />
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
    <Card className="space-y-4 p-5">
      <div>
        <div className="flex items-center gap-2">
          <p className="font-mono text-xl font-semibold text-brand">{detail.code}</p>
          <CopyButton value={detail.code} />
        </div>
        <p className="mt-1.5 text-sm leading-6 text-ink">{detail.description}</p>
      </div>

      <Section title="Hierarchy">
        <div className="space-y-1 text-sm text-ink">
          <HierRow
            label="Chapter"
            value={detail.hierarchy.chapter_code}
            extra={detail.chapter_name}
          />
          <HierRow label="Heading" value={detail.hierarchy.heading_code} />
          <HierRow label="Sub-heading" value={detail.hierarchy.subheading_code} />
          <HierRow
            label="Tariff line"
            value={detail.digit_level === 8 ? detail.normalized_code : null}
          />
        </div>
      </Section>

      {detail.import_policy || detail.export_policy || detail.policy_condition ? (
        <Section title="Policy notes">
          <div className="space-y-1 text-sm text-ink">
            {detail.import_policy ? <p>Import: {detail.import_policy}</p> : null}
            {detail.export_policy ? <p>Export: {detail.export_policy}</p> : null}
            {detail.policy_condition ? (
              <p className="text-ink-2">{detail.policy_condition}</p>
            ) : null}
          </div>
        </Section>
      ) : null}

      <div className="space-y-2 border-t border-line pt-4">
        <Button
          className="w-full"
          variant="secondary"
          loading={verifyPending}
          disabled={verified}
          onClick={onVerify}
        >
          {verified ? "Verification requested" : "Verify with CHA / customs broker"}
        </Button>
        <Button className="w-full" onClick={onUseForIncentives}>
          Use this HSN for Incentive Finder
        </Button>
        <Button className="w-full" variant="secondary" onClick={onUseForExportQuote}>
          Use in Export Quote calculator
        </Button>
        {!detail.incentive_rate_available ? (
          <p className="text-xs leading-5 text-ink-2">
            HSN exists, but no approved incentive/rate data is available for this code yet.
          </p>
        ) : null}
      </div>

      <p className="text-xs leading-5 text-ink-2">{detail.disclaimer}</p>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-panel border border-line bg-surface p-4">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function HierRow({
  label,
  value,
  extra,
}: {
  label: string;
  value: string | null;
  extra?: string | null;
}) {
  if (!value) return null;
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-xs text-ink-2">{label}</span>
      <span className="font-mono text-ink">
        {value}
        {extra ? <span className="ml-2 font-sans text-xs text-ink-2">{extra}</span> : null}
      </span>
    </div>
  );
}

function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="rounded border border-line-strong bg-surface-2 px-1.5 py-0.5 text-xs text-ink-2">
      {children}
    </span>
  );
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      className="rounded border border-line-strong px-1.5 py-0.5 text-xs text-ink-2 transition hover:border-brand hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function VerificationChip({ status }: { status: string }) {
  const map: Record<string, { label: string; tone: Tone }> = {
    cross_verified: { label: "Cross-verified", tone: "success" },
    exists_weak_match: { label: "Code exists · weak match", tone: "info" },
    unverified: { label: "Unverified by source", tone: "danger" },
  };
  const v = map[status] ?? map.unverified;
  return <Badge tone={v.tone}>{v.label}</Badge>;
}
