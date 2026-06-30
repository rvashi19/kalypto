import type {
  ComplianceCheckerRequest,
  ComplianceCoverageResponse,
  ComplianceRequirementInput,
  ExportQuoteRequest,
  HsnRateLookupResponse,
} from "@repo/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { AiBadge, inputCls, selectCls } from "../../lib/ui";

const MODULES = [
  {
    id: "hsn",
    title: "Incentive Finder",
    eyebrow: "Rates",
    summary: "Look up tenant-verified RoDTEP, Drawback, and RoSCTL records for a selected HSN. Classify codes in HSN Finder first.",
  },
  {
    id: "compliance",
    title: "Country Compliance Checker",
    eyebrow: "Requirements",
    summary: "Check destination documents, labels, certificates, inspections, and buyer questions.",
  },
  {
    id: "quote",
    title: "Landed Cost / Export Quote",
    eyebrow: "Calculator",
    summary: "Estimate buyer landed cost and exporter net realization from quote inputs.",
  },
  {
    id: "documents",
    title: "Document Builder",
    eyebrow: "PDF",
    summary: "Generate commercial invoice, proforma invoice, and packing list from shipments.",
  },
  {
    id: "verifier",
    title: "AI Document Verifier",
    eyebrow: "Audit",
    summary: "Upload shipment docs and compare fields before filing or claiming.",
  },
  {
    id: "claims",
    title: "Shipment & Claims Tracker",
    eyebrow: "Claims",
    summary: "Track money at risk, lock-risk findings, and shipment readiness.",
  },
  {
    id: "alerts",
    title: "Compliance Alerts",
    eyebrow: "Monitor",
    summary: "Review source changes, stale evidence, critical findings, and lock-risk signals.",
  },
] as const;

type ModuleId = (typeof MODULES)[number]["id"];

const DEFAULT_COMPLIANCE_FORM: ComplianceCheckerRequest = {
  product: "Dried red chilli flakes",
  hsn_code: "090422",
  destination_country: "USA",
  category: "spices",
  details: {
    retail_or_bulk: "retail",
    packaging_type: "pouch",
    processed_state: "dried",
  },
};

type QuoteForm = {
  product_name: string;
  hsn_code: string;
  destination_country: string;
  incoterm: string;
  quote_currency: string;
  fob_value: string;
  freight_value: string;
  insurance_value: string;
  destination_charges_value: string;
  domestic_charges_inr: string;
  destination_duty_percent: string;
  exchange_rate_to_inr: string;
};

const DEFAULT_QUOTE_FORM: QuoteForm = {
  product_name: "Cotton shirts",
  hsn_code: "610910",
  destination_country: "United Kingdom",
  incoterm: "CIF",
  quote_currency: "USD",
  fob_value: "10000",
  freight_value: "900",
  insurance_value: "80",
  destination_charges_value: "250",
  domestic_charges_inr: "30000",
  destination_duty_percent: "",
  exchange_rate_to_inr: "83",
};

function toNumber(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatMoney(value: number | null | undefined, currency = "INR") {
  if (value == null) return "Not available";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatCount(value: number | undefined) {
  return String(value ?? 0).padStart(2, "0");
}

function buildQuotePayload(form: QuoteForm): ExportQuoteRequest {
  return {
    product_name: form.product_name,
    hsn_code: form.hsn_code,
    destination_country: form.destination_country,
    incoterm: form.incoterm,
    quote_currency: form.quote_currency,
    fob_value: Number(form.fob_value),
    freight_value: toNumber(form.freight_value) ?? 0,
    insurance_value: toNumber(form.insurance_value) ?? 0,
    destination_charges_value: toNumber(form.destination_charges_value) ?? 0,
    domestic_charges_inr: toNumber(form.domestic_charges_inr) ?? 0,
    destination_duty_percent: toNumber(form.destination_duty_percent) ?? null,
    exchange_rate_to_inr: toNumber(form.exchange_rate_to_inr) ?? null,
  };
}

export function ToolsPage() {
  const { session, token, setSession } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [activeModule, setActiveModule] = useState<ModuleId>("hsn");
  const [hsn, setHsn] = useState(searchParams.get("hsn") ?? "090422");

  // When the HSN Finder hands off a selected code (/tools?hsn=...), prefill the
  // incentive lookup and focus this module.
  useEffect(() => {
    const handoff = searchParams.get("hsn");
    if (handoff) {
      setHsn(handoff);
      setActiveModule("hsn");
    }
  }, [searchParams]);

  const [hsnFobValue, setHsnFobValue] = useState("100000");
  const [complianceForm, setComplianceForm] =
    useState<ComplianceCheckerRequest>(DEFAULT_COMPLIANCE_FORM);
  const [quoteForm, setQuoteForm] = useState<QuoteForm>(DEFAULT_QUOTE_FORM);
  const [selectedChangeId, setSelectedChangeId] = useState<string | null>(null);
  const [evidenceJson, setEvidenceJson] = useState("");

  const shipmentsQuery = useQuery({
    queryKey: ["shipments", token],
    queryFn: () => api.listShipments(token!),
    enabled: Boolean(token),
  });

  const discrepancyQuery = useQuery({
    queryKey: ["discrepancy-dashboard", token],
    queryFn: () => api.discrepancyDashboard(token!),
    enabled: Boolean(token),
  });

  const optionsQuery = useQuery({
    queryKey: ["compliance-options", token],
    queryFn: () => api.complianceOptions(token!),
    enabled: Boolean(token),
  });

  const dueSourcesQuery = useQuery({
    queryKey: ["compliance-due-sources", token],
    queryFn: () => api.dueComplianceSources(token!),
    enabled: Boolean(token && session?.membership.role !== "read_only"),
  });

  const sourceChangesQuery = useQuery({
    queryKey: ["compliance-source-changes", token],
    queryFn: () => api.sourceChanges(token!),
    enabled: Boolean(token && session?.membership.role !== "read_only"),
  });

  const coverageQuery = useQuery({
    queryKey: ["compliance-coverage", token],
    queryFn: () => api.complianceCoverage(token!),
    enabled: Boolean(token && session?.membership.role !== "read_only"),
  });

  const sourceChangeDetailQuery = useQuery({
    queryKey: ["compliance-source-change-detail", selectedChangeId, token],
    queryFn: () => api.sourceChangeDetail(selectedChangeId!, token!),
    enabled: Boolean(token && selectedChangeId),
  });

  const hsnMutation = useMutation({
    mutationFn: () => api.getHsnRates(hsn, token!, toNumber(hsnFobValue)),
  });

  const complianceMutation = useMutation({
    mutationFn: () => api.askComplianceChecker(complianceForm, token!),
  });

  const quoteMutation = useMutation({
    mutationFn: () => api.calculateExportQuote(buildQuotePayload(quoteForm), token!),
  });

  const scrapeMutation = useMutation({
    mutationFn: (source: { source_url: string; country: string; category: string }) =>
      api.runComplianceScrape(source, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["compliance-due-sources"] });
      queryClient.invalidateQueries({ queryKey: ["compliance-source-changes"] });
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({
      changeId,
      status,
    }: {
      changeId: string;
      status: "reviewed" | "ignored";
    }) => api.reviewSourceChange(changeId, { status }, token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["compliance-source-changes"] });
      queryClient.invalidateQueries({ queryKey: ["compliance-coverage"] });
    },
  });

  const ingestEvidenceMutation = useMutation({
    mutationFn: () => {
      const parsed = JSON.parse(evidenceJson) as unknown;
      const records = (
        Array.isArray(parsed)
          ? parsed
          : typeof parsed === "object" && parsed !== null && "records" in parsed
            ? (parsed as { records: unknown }).records
            : null
      ) as ComplianceRequirementInput[] | null;
      if (!Array.isArray(records) || records.length === 0) {
        throw new Error("Paste a JSON array of reviewed compliance requirement records.");
      }
      return api.ingestComplianceRecords(records, token!);
    },
    onSuccess: () => {
      setEvidenceJson("");
      queryClient.invalidateQueries({ queryKey: ["compliance-coverage"] });
      queryClient.invalidateQueries({ queryKey: ["compliance-options"] });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });

  const shipments = shipmentsQuery.data ?? [];
  const recentShipments = shipments.slice(0, 4);
  const criticalAlerts = discrepancyQuery.data?.critical ?? 0;
  const lockRisk = discrepancyQuery.data?.lock_risk ?? 0;
  const dueSources = dueSourcesQuery.data ?? [];
  const sourceChanges = sourceChangesQuery.data ?? [];

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <section className="relative mb-6 overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 px-5 py-6 shadow-2xl shadow-slate-950/20 md:px-8">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_12%,rgba(34,211,238,0.12),transparent_28%),radial-gradient(circle_at_86%_8%,rgba(20,184,166,0.1),transparent_30%),linear-gradient(135deg,rgba(15,23,42,0.35),rgba(2,6,23,0.92))]" />
        <div className="relative grid gap-6 lg:grid-cols-[1fr_360px] lg:items-end">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.34em] text-cyan-200">
              Export assurance workspace
            </p>
            <h1 className="mt-4 max-w-3xl text-3xl font-semibold tracking-[-0.035em] text-white md:text-5xl">
              Practical tools for documentation, compliance, incentives, and claims.
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300 md:text-base">
              Work through the export lifecycle without losing evidence: rate lookup, destination
              requirements, quote calculations, document generation, verification, claim tracking,
              and compliance review.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <SignalCard label="Shipments" value={formatCount(shipments.length)} tone="cyan" />
            <SignalCard label="Critical" value={formatCount(criticalAlerts)} tone="rose" />
            <SignalCard label="Lock risk" value={formatCount(lockRisk)} tone="amber" />
            <SignalCard label="Sources due" value={formatCount(dueSources.length)} tone="emerald" />
          </div>
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <aside className="space-y-3">
          {MODULES.map((module, index) => (
            <button
              key={module.id}
              onClick={() => setActiveModule(module.id)}
              className={`group w-full rounded-2xl border p-4 text-left transition-all ${
                activeModule === module.id
                  ? "border-cyan-300/35 bg-cyan-300/10 shadow-lg shadow-cyan-950/20"
                  : "border-white/10 bg-slate-900/65 hover:border-white/20 hover:bg-slate-900"
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border text-xs font-black ${
                    activeModule === module.id
                      ? "border-cyan-300/40 bg-cyan-300/15 text-cyan-200"
                      : "border-white/10 bg-slate-950 text-slate-500 group-hover:text-slate-300"
                  }`}
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.26em] text-slate-500">
                    {module.eyebrow}
                  </p>
                  <h2 className="mt-1 text-sm font-semibold text-slate-100">{module.title}</h2>
                  <p className="mt-1 text-xs leading-5 text-slate-500">{module.summary}</p>
                </div>
              </div>
            </button>
          ))}
        </aside>

        <section>
          {activeModule === "hsn" ? (
            <HsnFinderPanel
              hsn={hsn}
              hsnFobValue={hsnFobValue}
              result={hsnMutation.data}
              isPending={hsnMutation.isPending}
              error={hsnMutation.error}
              onHsnChange={setHsn}
              onFobChange={setHsnFobValue}
              onLookup={() => hsnMutation.mutate()}
            />
          ) : null}

          {activeModule === "compliance" ? (
            <ComplianceCheckerPanel
              form={complianceForm}
              countries={optionsQuery.data?.countries ?? []}
              categories={optionsQuery.data?.categories ?? []}
              isPending={complianceMutation.isPending}
              error={complianceMutation.error}
              result={complianceMutation.data}
              onChange={setComplianceForm}
              onCheck={() => complianceMutation.mutate()}
            />
          ) : null}

          {activeModule === "quote" ? (
            <QuotePanel
              form={quoteForm}
              isPending={quoteMutation.isPending}
              error={quoteMutation.error}
              result={quoteMutation.data}
              onChange={setQuoteForm}
              onCalculate={() => quoteMutation.mutate()}
            />
          ) : null}

          {activeModule === "documents" ? (
            <ShipmentActionPanel
              title="Document Builder"
              description="Open a shipment, generate export PDFs, then download the draft for review/signature."
              emptyText="Create a shipment first, then generate documents from its Documents step."
              shipments={recentShipments}
              actionLabel="Build docs"
              footer={
                <Link to="/shipments/new">
                  <Button>Create shipment</Button>
                </Link>
              }
            />
          ) : null}

          {activeModule === "verifier" ? (
            <ShipmentActionPanel
              title="AI Document Verifier"
              description="Upload commercial invoice, packing list, shipping bill, and support docs, then run AI plus deterministic checks."
              emptyText="No shipments available for document verification yet."
              shipments={recentShipments}
              actionLabel="Verify docs"
              badge={<AiBadge />}
              footer={
                <p className="text-xs leading-5 text-slate-500">
                  AI reports are decision-support. Deterministic reconciliation remains the system
                  of record for claim-risk findings.
                </p>
              }
            />
          ) : null}

          {activeModule === "claims" ? (
            <ClaimsPanel shipments={recentShipments} discrepancies={discrepancyQuery.data} />
          ) : null}

          {activeModule === "alerts" ? (
            <AlertsPanel
              dueSources={dueSources}
              sourceChanges={sourceChanges}
              coverage={coverageQuery.data}
              selectedChangeId={selectedChangeId}
              selectedChangeDetail={sourceChangeDetailQuery.data}
              evidenceJson={evidenceJson}
              discrepancyTotal={discrepancyQuery.data?.total ?? 0}
              critical={criticalAlerts}
              lockRisk={lockRisk}
              isScraping={scrapeMutation.isPending}
              isReviewing={reviewMutation.isPending}
              isIngesting={ingestEvidenceMutation.isPending}
              ingestResult={ingestEvidenceMutation.data}
              ingestError={ingestEvidenceMutation.error}
              onScrape={(source) => scrapeMutation.mutate(source)}
              onSelectChange={setSelectedChangeId}
              onReview={(changeId, status) => reviewMutation.mutate({ changeId, status })}
              onEvidenceJsonChange={setEvidenceJson}
              onIngestEvidence={() => ingestEvidenceMutation.mutate()}
            />
          ) : null}
        </section>
      </div>
    </DashboardShell>
  );
}

function SignalCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "cyan" | "rose" | "amber" | "emerald";
}) {
  const toneClass = {
    cyan: "text-cyan-100 border-cyan-300/20 bg-cyan-300/10",
    rose: "text-rose-100 border-rose-300/20 bg-rose-300/10",
    amber: "text-amber-100 border-amber-300/20 bg-amber-300/10",
    emerald: "text-emerald-100 border-emerald-300/20 bg-emerald-300/10",
  }[tone];

  return (
    <div className={`rounded-2xl border px-4 py-3 ${toneClass}`}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] opacity-75">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-[-0.04em]">{value}</p>
    </div>
  );
}

function PanelFrame({
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
    <Card className="overflow-hidden border-white/10 bg-slate-900/80">
      <div className="h-px bg-gradient-to-r from-transparent via-cyan-200/50 to-transparent" />
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-xl tracking-[-0.02em]">{title}</CardTitle>
          {badge}
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </span>
      {children}
      {hint ? <span className="block text-xs text-slate-600">{hint}</span> : null}
    </label>
  );
}

function HsnFinderPanel({
  hsn,
  hsnFobValue,
  result,
  isPending,
  error,
  onHsnChange,
  onFobChange,
  onLookup,
}: {
  hsn: string;
  hsnFobValue: string;
  result: HsnRateLookupResponse | undefined;
  isPending: boolean;
  error: unknown;
  onHsnChange: (value: string) => void;
  onFobChange: (value: string) => void;
  onLookup: () => void;
}) {
  return (
    <PanelFrame
      title="Incentive Finder"
      description="Look up approved incentive/rate records for an HSN code. Use HSN Finder to classify the code first. No model-generated rates."
    >
      <div className="grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
        <Field label="HSN code">
          <input className={inputCls} value={hsn} onChange={(event) => onHsnChange(event.target.value)} />
        </Field>
        <Field label="FOB basis in INR" hint="Used only for incentive estimates.">
          <input
            className={inputCls}
            type="number"
            value={hsnFobValue}
            onChange={(event) => onFobChange(event.target.value)}
          />
        </Field>
        <Button disabled={isPending || hsn.length < 4} onClick={onLookup}>
          {isPending ? "Looking up..." : "Find rates"}
        </Button>
      </div>
      {error instanceof Error ? <ErrorBox message={error.message} /> : null}
      {result ? (
        <div className="mt-5 grid gap-4 lg:grid-cols-[280px_1fr]">
          <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-5">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
              Finder status
            </p>
            <p className={`mt-3 text-2xl font-black ${result.found ? "text-emerald-300" : "text-amber-300"}`}>
              {result.found ? "Approved source found" : "No approved source"}
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-400">{result.message ?? result.notes}</p>
            {!result.found ? (
              <div className="mt-4 rounded-xl border border-amber-300/20 bg-amber-300/10 p-3 text-xs leading-5 text-amber-100">
                Import the latest official DGFT/CBIC schedule, keep it as pending, and approve it
                only after operator review. Client screens never show pending or expired rows.
              </div>
            ) : null}
            <p className="mt-4 text-xs leading-5 text-amber-300">{result.disclaimer}</p>
          </div>
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <Metric label="RoDTEP" value={result.rodtep_rate != null ? `${result.rodtep_rate}%` : "N/A"} />
              <Metric
                label="Drawback AIR"
                value={result.duty_drawback_rate != null ? `${result.duty_drawback_rate}%` : "N/A"}
              />
              <Metric label="RoSCTL" value={result.rosctl_rate != null ? `${result.rosctl_rate}%` : "N/A"} />
              {result.estimated_amounts_inr
                ? Object.entries(result.estimated_amounts_inr).map(([scheme, amount]) => (
                    <Metric
                      key={scheme}
                      label={`Est. ${scheme.replaceAll("_", " ")}`}
                      value={formatMoney(amount)}
                    />
                  ))
                : null}
            </div>
            {result.rate_evidence?.length ? (
              <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                  Source evidence
                </p>
                <div className="mt-3 grid gap-3">
                  {result.rate_evidence.map((row) => (
                    <div key={`${row.scheme}-${row.version_stamp}`} className="rounded-xl bg-white/[0.03] p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-semibold text-slate-100">
                          {row.scheme} · {row.rate}%
                        </p>
                        <span className="rounded-full border border-emerald-300/25 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-200">
                          {row.review_status}
                        </span>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-400">
                        {row.source} · effective {row.effective_date}
                        {row.expires_at ? ` · expires ${row.expires_at}` : ""}
                      </p>
                      {row.source_url ? (
                        <a
                          className="mt-2 inline-block text-xs font-semibold text-cyan-200 hover:text-cyan-100"
                          href={row.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open official/source evidence
                        </a>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </PanelFrame>
  );
}

function ComplianceCheckerPanel({
  form,
  countries,
  categories,
  isPending,
  error,
  result,
  onChange,
  onCheck,
}: {
  form: ComplianceCheckerRequest;
  countries: string[];
  categories: string[];
  isPending: boolean;
  error: unknown;
  result: Awaited<ReturnType<typeof api.askComplianceChecker>> | undefined;
  onChange: (value: ComplianceCheckerRequest) => void;
  onCheck: () => void;
}) {
  const detailsText = Object.entries(form.details ?? {})
    .map(([key, value]) => `${key}: ${value ?? ""}`)
    .join("\n");

  return (
    <PanelFrame
      title="Country Compliance Requirement Checker"
      description="The checker returns source-backed requirements, unanswered questions, and confidence."
      badge={<AiBadge />}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Product">
          <input
            className={inputCls}
            value={form.product}
            onChange={(event) => onChange({ ...form, product: event.target.value })}
          />
        </Field>
        <Field label="HSN">
          <input
            className={inputCls}
            value={form.hsn_code ?? ""}
            onChange={(event) => onChange({ ...form, hsn_code: event.target.value })}
          />
        </Field>
        <Field label="Destination">
          <select
            className={selectCls}
            value={form.destination_country}
            onChange={(event) => onChange({ ...form, destination_country: event.target.value })}
          >
            {[form.destination_country, ...countries]
              .filter((value, index, list) => value && list.indexOf(value) === index)
              .map((country) => (
                <option key={country}>{country}</option>
              ))}
          </select>
        </Field>
        <Field label="Category">
          <select
            className={selectCls}
            value={form.category}
            onChange={(event) => onChange({ ...form, category: event.target.value })}
          >
            {[form.category, ...categories]
              .filter((value, index, list) => value && list.indexOf(value) === index)
              .map((category) => (
                <option key={category}>{category}</option>
              ))}
          </select>
        </Field>
        <Field label="Extra facts">
          <textarea
            className="min-h-28 w-full rounded-md border border-white/10 bg-slate-950/80 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-cyan-300/60"
            value={detailsText}
            onChange={(event) =>
              onChange({
                ...form,
                details: Object.fromEntries(
                  event.target.value
                    .split("\n")
                    .map((line) => line.trim())
                    .filter(Boolean)
                    .map((line) => {
                      const [key, ...rest] = line.split(":");
                      return [key.trim(), rest.join(":").trim()];
                    }),
                ),
              })
            }
          />
        </Field>
        <div className="flex items-end">
          <Button className="w-full" disabled={isPending} onClick={onCheck}>
            {isPending ? "Checking..." : "Check requirements"}
          </Button>
        </div>
      </div>
      {error instanceof Error ? <ErrorBox message={error.message} /> : null}
      {result ? (
        <div className="mt-5 space-y-4">
          <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="font-semibold text-slate-100">{result.confidence_level} confidence</p>
              <span className="rounded-full border border-white/10 px-3 py-1 text-xs uppercase tracking-widest text-slate-400">
                {result.status.replaceAll("_", " ")}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-400">{result.answer}</p>
          </div>
          <ResultColumns
            groups={[
              ["Import docs", result.sections.required_import_documents],
              ["Certificates", result.sections.certificates_required],
              ["Labeling", result.sections.labeling_requirements],
              ["Restrictions", result.sections.restriction_alerts],
              ["Buyer questions", result.sections.buyer_side_questions],
              ["Unresolved", result.unresolved_questions],
            ]}
          />
        </div>
      ) : null}
    </PanelFrame>
  );
}

function QuotePanel({
  form,
  isPending,
  error,
  result,
  onChange,
  onCalculate,
}: {
  form: QuoteForm;
  isPending: boolean;
  error: unknown;
  result: Awaited<ReturnType<typeof api.calculateExportQuote>> | undefined;
  onChange: (value: QuoteForm) => void;
  onCalculate: () => void;
}) {
  function set(key: keyof QuoteForm, value: string) {
    onChange({ ...form, [key]: value });
  }

  return (
    <PanelFrame
      title="Landed Cost / Export Quote Calculator"
      description="Estimate quote totals and exporter realization without guessing legal duty data."
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Field label="Product"><input className={inputCls} value={form.product_name} onChange={(e) => set("product_name", e.target.value)} /></Field>
        <Field label="HSN"><input className={inputCls} value={form.hsn_code} onChange={(e) => set("hsn_code", e.target.value)} /></Field>
        <Field label="Destination"><input className={inputCls} value={form.destination_country} onChange={(e) => set("destination_country", e.target.value)} /></Field>
        <Field label="Incoterm"><input className={inputCls} value={form.incoterm} onChange={(e) => set("incoterm", e.target.value)} /></Field>
        <Field label="Currency"><input className={inputCls} value={form.quote_currency} onChange={(e) => set("quote_currency", e.target.value)} /></Field>
        <Field label="FOB value"><input className={inputCls} type="number" value={form.fob_value} onChange={(e) => set("fob_value", e.target.value)} /></Field>
        <Field label="Freight"><input className={inputCls} type="number" value={form.freight_value} onChange={(e) => set("freight_value", e.target.value)} /></Field>
        <Field label="Insurance"><input className={inputCls} type="number" value={form.insurance_value} onChange={(e) => set("insurance_value", e.target.value)} /></Field>
        <Field label="Destination charges"><input className={inputCls} type="number" value={form.destination_charges_value} onChange={(e) => set("destination_charges_value", e.target.value)} /></Field>
        <Field label="Destination duty %" hint="Use broker-confirmed value only."><input className={inputCls} type="number" value={form.destination_duty_percent} onChange={(e) => set("destination_duty_percent", e.target.value)} /></Field>
        <Field label="FX to INR"><input className={inputCls} type="number" value={form.exchange_rate_to_inr} onChange={(e) => set("exchange_rate_to_inr", e.target.value)} /></Field>
        <Field label="Domestic charges INR"><input className={inputCls} type="number" value={form.domestic_charges_inr} onChange={(e) => set("domestic_charges_inr", e.target.value)} /></Field>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button disabled={isPending || !form.fob_value || !form.hsn_code} onClick={onCalculate}>
          {isPending ? "Calculating..." : "Calculate quote"}
        </Button>
        <p className="text-xs text-slate-500">
          Incentives appear only when tenant-verified rates and INR basis exist.
        </p>
      </div>
      {error instanceof Error ? <ErrorBox message={error.message} /> : null}
      {result ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_360px]">
          <div className="grid gap-3 sm:grid-cols-2">
            <Metric
              label="CIF basis"
              value={formatMoney(result.cif_value, result.quote_currency)}
            />
            <Metric
              label="Buyer landed estimate"
              value={formatMoney(result.buyer_landed_estimate, result.quote_currency)}
            />
            <Metric label="Incentive total" value={formatMoney(result.incentive_total_inr)} />
            <Metric
              label="Exporter net INR"
              value={formatMoney(result.exporter_net_realization_inr)}
            />
          </div>
          <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
            <p className="text-sm font-semibold text-slate-100">Calculation trail</p>
            <div className="mt-3 space-y-2">
              {result.line_items.map((item) => (
                <div key={`${item.label}-${item.currency}`} className="flex justify-between gap-3 text-sm">
                  <span className="text-slate-500">{item.label}</span>
                  <span className="font-medium text-slate-200">
                    {formatMoney(item.amount, item.currency)}
                  </span>
                </div>
              ))}
            </div>
          </div>
          {result.incentive_estimates.length ? (
            <div className="xl:col-span-2">
              <ResultColumns
                groups={[
                  [
                    "Incentive estimates",
                    result.incentive_estimates.map(
                      (item) =>
                        `${item.scheme}: ${formatMoney(item.estimated_amount_inr)} at ${item.rate_percent}% (${item.version_stamp})`,
                    ),
                  ],
                  ["Warnings", result.warnings],
                ]}
              />
            </div>
          ) : (
            <div className="xl:col-span-2">
              <ResultColumns groups={[["Warnings", result.warnings]]} />
            </div>
          )}
          <p className="text-xs leading-5 text-amber-300 xl:col-span-2">{result.disclaimer}</p>
        </div>
      ) : null}
    </PanelFrame>
  );
}

function ShipmentActionPanel({
  title,
  description,
  emptyText,
  shipments,
  actionLabel,
  badge,
  footer,
}: {
  title: string;
  description: string;
  emptyText: string;
  shipments: Array<{ id: string; product_name: string; hsn_code: string; destination_country: string }>;
  actionLabel: string;
  badge?: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <PanelFrame title={title} description={description} badge={badge}>
      {!shipments.length ? (
        <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/60 p-8 text-center">
          <p className="text-sm text-slate-500">{emptyText}</p>
          <div className="mt-4">{footer}</div>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {shipments.map((shipment) => (
            <Link
              key={shipment.id}
              to={`/shipments/${shipment.id}`}
              className="rounded-2xl border border-white/8 bg-slate-950/60 p-4 transition hover:border-cyan-300/30 hover:bg-cyan-300/5"
            >
              <p className="font-semibold text-slate-100">{shipment.product_name}</p>
              <p className="mt-1 text-xs text-slate-500">
                HSN {shipment.hsn_code} / {shipment.destination_country}
              </p>
              <p className="mt-4 text-sm font-semibold text-cyan-300">{actionLabel} - open</p>
            </Link>
          ))}
        </div>
      )}
      {shipments.length && footer ? <div className="mt-4">{footer}</div> : null}
    </PanelFrame>
  );
}

function ClaimsPanel({
  shipments,
  discrepancies,
}: {
  shipments: Array<{ id: string; product_name: string; destination_country: string; fob_value: number | null; invoice_currency: string }>;
  discrepancies:
    | Awaited<ReturnType<typeof api.discrepancyDashboard>>
    | undefined;
}) {
  return (
    <PanelFrame
      title="Shipment & Claims Tracker"
      description="A practical view of what needs attention before claims or refunds get locked."
    >
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Findings" value={String(discrepancies?.total ?? 0)} />
        <Metric label="Critical" value={String(discrepancies?.critical ?? 0)} />
        <Metric label="Lock risk" value={String(discrepancies?.lock_risk ?? 0)} />
        <Metric label="Money at risk" value={formatMoney(discrepancies?.potential_amount ?? 0)} />
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
          <p className="text-sm font-semibold text-slate-100">Recent shipments</p>
          <div className="mt-3 space-y-2">
            {shipments.length ? (
              shipments.map((shipment) => (
                <Link
                  key={shipment.id}
                  to={`/shipments/${shipment.id}`}
                  className="flex items-center justify-between rounded-xl border border-white/6 px-3 py-2 hover:border-cyan-300/30"
                >
                  <span>
                    <span className="block text-sm text-slate-200">{shipment.product_name}</span>
                    <span className="text-xs text-slate-500">{shipment.destination_country}</span>
                  </span>
                  <span className="text-xs text-slate-400">
                    {formatMoney(shipment.fob_value, shipment.invoice_currency)}
                  </span>
                </Link>
              ))
            ) : (
              <p className="text-sm text-slate-500">No shipments yet.</p>
            )}
          </div>
        </div>
        <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
          <p className="text-sm font-semibold text-slate-100">Latest findings</p>
          <div className="mt-3 space-y-2">
            {discrepancies?.items.length ? (
              discrepancies.items.slice(0, 5).map((item) => (
                <Link
                  key={item.id}
                  to={`/shipments/${item.shipment_id}`}
                  className="block rounded-xl border border-white/6 px-3 py-2 hover:border-amber-300/30"
                >
                  <span className="block text-sm text-slate-200">{item.message}</span>
                  <span className="mt-1 block text-xs capitalize text-slate-500">
                    {item.severity} / {item.type.replaceAll("_", " ")}
                  </span>
                </Link>
              ))
            ) : (
              <p className="text-sm text-slate-500">No persisted findings yet. Run reconciliation on a shipment.</p>
            )}
          </div>
        </div>
      </div>
    </PanelFrame>
  );
}

function AlertsPanel({
  dueSources,
  sourceChanges,
  coverage,
  selectedChangeId,
  selectedChangeDetail,
  evidenceJson,
  discrepancyTotal,
  critical,
  lockRisk,
  isScraping,
  isReviewing,
  isIngesting,
  ingestResult,
  ingestError,
  onScrape,
  onSelectChange,
  onReview,
  onEvidenceJsonChange,
  onIngestEvidence,
}: {
  dueSources: Array<{ source_url: string; country: string; category: string; last_checked_at: string | null }>;
  sourceChanges: Array<{ id: string; source_url: string; country: string; category: string; created_at: string }>;
  coverage: ComplianceCoverageResponse | undefined;
  selectedChangeId: string | null;
  selectedChangeDetail:
    | Awaited<ReturnType<typeof api.sourceChangeDetail>>
    | undefined;
  evidenceJson: string;
  discrepancyTotal: number;
  critical: number;
  lockRisk: number;
  isScraping: boolean;
  isReviewing: boolean;
  isIngesting: boolean;
  ingestResult: Awaited<ReturnType<typeof api.ingestComplianceRecords>> | undefined;
  ingestError: unknown;
  onScrape: (source: { source_url: string; country: string; category: string }) => void;
  onSelectChange: (changeId: string | null) => void;
  onReview: (changeId: string, status: "reviewed" | "ignored") => void;
  onEvidenceJsonChange: (value: string) => void;
  onIngestEvidence: () => void;
}) {
  const coverageCells = coverage?.cells ?? [];
  const statusStyles = {
    verified: "border-emerald-300/25 bg-emerald-300/10 text-emerald-200",
    partial: "border-cyan-300/25 bg-cyan-300/10 text-cyan-200",
    needs_review: "border-amber-300/25 bg-amber-300/10 text-amber-200",
    empty: "border-slate-700 bg-slate-950 text-slate-500",
  } as const;

  return (
    <PanelFrame
      title="Compliance Alerts"
      description="Operational alerts for stale sources, source changes, and claim-risk findings."
    >
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label="Total findings" value={String(discrepancyTotal)} />
        <Metric label="Critical findings" value={String(critical)} />
        <Metric label="Lock-risk findings" value={String(lockRisk)} />
      </div>
      {coverage ? (
        <div className="mt-5 rounded-2xl border border-white/8 bg-slate-950/60 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-100">Compliance coverage matrix</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Refresh interval: every {coverage.refresh_interval_days} days / due sources:{" "}
                {coverage.due_sources_count} / changes needing review:{" "}
                {coverage.source_changes_needing_review}
              </p>
            </div>
            <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-xs text-amber-200">
              Review-first data
            </span>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {coverageCells.map((cell) => (
              <div
                key={`${cell.country}-${cell.category}`}
                className={`rounded-xl border p-3 ${statusStyles[cell.status]}`}
              >
                <p className="text-xs font-bold uppercase tracking-[0.18em] opacity-75">
                  {cell.status.replaceAll("_", " ")}
                </p>
                <p className="mt-1 text-sm font-semibold text-slate-100">
                  {cell.country} / {cell.category}
                </p>
                <p className="mt-1 text-xs opacity-80">
                  {cell.approved_fresh_records} fresh / {cell.pending_or_draft_records} pending /{" "}
                  {cell.stale_records} stale / {cell.official_sources} official source(s)
                </p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs leading-5 text-slate-600">{coverage.disclaimer}</p>
        </div>
      ) : null}
      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
          <p className="text-sm font-semibold text-slate-100">Source refresh queue</p>
          <div className="mt-3 space-y-2">
            {dueSources.length ? (
              dueSources.slice(0, 6).map((source) => (
                <div key={`${source.source_url}-${source.country}`} className="rounded-xl border border-white/6 p-3">
                  <p className="truncate text-sm text-slate-200">{source.source_url}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {source.country} / {source.category} / checked {source.last_checked_at ?? "never"}
                  </p>
                  <Button
                    className="mt-2"
                    size="sm"
                    variant="secondary"
                    disabled={isScraping}
                    onClick={() => onScrape(source)}
                  >
                    Refresh source
                  </Button>
                </div>
              ))
            ) : (
              <p className="text-sm text-emerald-300">No sources are due right now.</p>
            )}
          </div>
        </div>
        <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
          <p className="text-sm font-semibold text-slate-100">Change review queue</p>
          <div className="mt-3 space-y-2">
            {sourceChanges.length ? (
              sourceChanges.slice(0, 6).map((change) => (
                <div key={change.id} className="rounded-xl border border-amber-300/20 bg-amber-300/5 p-3">
                  <p className="truncate text-sm text-slate-200">{change.source_url}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {change.country} / {change.category} / {new Date(change.created_at).toLocaleString()}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() =>
                        onSelectChange(selectedChangeId === change.id ? null : change.id)
                      }
                    >
                      {selectedChangeId === change.id ? "Hide evidence" : "View evidence"}
                    </Button>
                    <Button
                      size="sm"
                      disabled={isReviewing}
                      onClick={() => onReview(change.id, "reviewed")}
                    >
                      Mark reviewed
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={isReviewing}
                      onClick={() => onReview(change.id, "ignored")}
                    >
                      Ignore change
                    </Button>
                  </div>
                  {selectedChangeId === change.id && selectedChangeDetail ? (
                    <div className="mt-3 grid gap-3 text-xs">
                      <div className="rounded-xl border border-white/8 bg-slate-950/70 p-3">
                        <p className="font-semibold text-slate-200">
                          Current snapshot: {selectedChangeDetail.current_title}
                        </p>
                        <p className="mt-1 text-slate-500">
                          Scraped{" "}
                          {new Date(selectedChangeDetail.current_scraped_at).toLocaleString()}
                        </p>
                        <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 text-slate-300">
                          {selectedChangeDetail.current_markdown_excerpt}
                        </pre>
                      </div>
                      {selectedChangeDetail.previous_markdown_excerpt ? (
                        <div className="rounded-xl border border-white/8 bg-slate-950/70 p-3">
                          <p className="font-semibold text-slate-200">
                            Previous snapshot: {selectedChangeDetail.previous_title ?? "Untitled"}
                          </p>
                          <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 text-slate-500">
                            {selectedChangeDetail.previous_markdown_excerpt}
                          </pre>
                        </div>
                      ) : null}
                      <p className="text-amber-200">{selectedChangeDetail.excerpt_notice}</p>
                    </div>
                  ) : null}
                </div>
              ))
            ) : (
              <p className="text-sm text-emerald-300">No scraped changes need review.</p>
            )}
          </div>
        </div>
      </div>
      <div className="mt-5 rounded-2xl border border-white/8 bg-slate-950/60 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-100">Reviewed evidence ingest</p>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">
              Paste reviewed compliance requirement JSON after checking the official source. Use
              `review_status: "approved"` only when a human operator has verified the wording.
            </p>
          </div>
          <Button
            size="sm"
            disabled={isIngesting || !evidenceJson.trim()}
            onClick={onIngestEvidence}
          >
            {isIngesting ? "Ingesting..." : "Ingest evidence"}
          </Button>
        </div>
        <textarea
          className="mt-4 min-h-48 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-3 font-mono text-xs leading-5 text-slate-200 outline-none focus:ring-2 focus:ring-cyan-300/50"
          value={evidenceJson}
          onChange={(event) => onEvidenceJsonChange(event.target.value)}
          placeholder={`[
  {
    "country": "USA",
    "category": "spices",
    "hsn_code": "0904",
    "product_keywords": ["chilli", "spice"],
    "requirement_type": "labeling",
    "requirement_text": "Operator-reviewed requirement text from the official source.",
    "source_url": "https://official-source.example/page",
    "source_name": "Official authority page",
    "source_authority_level": "official",
    "confidence_score": 80,
    "review_status": "approved",
    "reviewed_by": "operator@example.com"
  }
]`}
        />
        {ingestResult ? (
          <p className="mt-3 text-sm text-emerald-300">
            Ingested {ingestResult.total} record(s): {ingestResult.created} created,{" "}
            {ingestResult.updated} updated.
          </p>
        ) : null}
        {ingestError instanceof Error ? (
          <p className="mt-3 text-sm text-rose-300">{ingestError.message}</p>
        ) : null}
      </div>
    </PanelFrame>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
      <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-black text-slate-100">{value}</p>
    </div>
  );
}

function ResultColumns({ groups }: { groups: Array<[string, string[]]> }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {groups.map(([title, values]) => (
        <div key={title} className="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
          <p className="text-sm font-semibold text-slate-100">{title}</p>
          <div className="mt-3 space-y-2">
            {values.length ? (
              values.map((value, index) => (
                <p key={`${title}-${index}`} className="rounded-xl border border-white/6 bg-slate-900/70 p-3 text-sm leading-6 text-slate-300">
                  {value}
                </p>
              ))
            ) : (
              <p className="text-sm text-slate-500">No items returned.</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="mt-4 rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm leading-6 text-rose-100">
      {message}
    </div>
  );
}
