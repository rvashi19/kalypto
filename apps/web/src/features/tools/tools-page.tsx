import type { ComplianceCheckerRequest, ComplianceRequirementInput } from "@repo/shared";
import { Badge, Button, PageHeader } from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useLogout } from "../../lib/use-logout";
import { AiBadge } from "../../lib/ui";
import { ComplianceCheckerPanel, HsnFinderPanel, QuotePanel } from "./tools-lookup-panels";
import { AlertsPanel, ClaimsPanel, ShipmentActionPanel } from "./tools-ops-panels";
import { buildQuotePayload, DEFAULT_QUOTE_FORM, toNumber, type QuoteForm } from "./tools-utils";

function formatCount(value: number | undefined) {
  return String(value ?? 0);
}

const MODULES = [
  {
    id: "hsn",
    title: "Incentive Finder",
    summary:
      "Look up tenant-verified RoDTEP, Drawback, and RoSCTL records for a selected HSN. Classify codes in HSN Finder first.",
  },
  {
    id: "compliance",
    title: "Country Compliance Checker",
    summary: "Check destination documents, labels, certificates, inspections, and buyer questions.",
  },
  {
    id: "quote",
    title: "Landed Cost / Export Quote",
    summary: "Estimate buyer landed cost and exporter net realization from quote inputs.",
  },
  {
    id: "documents",
    title: "Document Builder",
    summary: "Generate commercial invoice, proforma invoice, and packing list from shipments.",
  },
  {
    id: "verifier",
    title: "AI Document Verifier",
    summary: "Upload shipment docs and compare fields before filing or claiming.",
  },
  {
    id: "claims",
    title: "Shipment & Claims Tracker",
    summary: "Track money at risk, lock-risk findings, and shipment readiness.",
  },
  {
    id: "alerts",
    title: "Compliance Alerts",
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

export function ToolsPage() {
  const { session, token } = useAuth();
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
    mutationFn: ({ changeId, status }: { changeId: string; status: "reviewed" | "ignored" }) =>
      api.reviewSourceChange(changeId, { status }, token!),
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

  const logoutMutation = useLogout();

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
      <PageHeader
        title="Tools"
        breadcrumbs={[{ label: "Workspace" }, { label: "Tools" }]}
        meta={
          <>
            <span>
              Rate lookup, requirements, quotes, documents, verification and compliance review.
            </span>
            <Badge tone="info">{formatCount(shipments.length)} shipments</Badge>
            <Badge tone={criticalAlerts ? "danger" : "success"}>
              {formatCount(criticalAlerts)} critical
            </Badge>
            <Badge tone={lockRisk ? "warning" : "success"}>{formatCount(lockRisk)} lock risk</Badge>
            <Badge tone={dueSources.length ? "warning" : "success"}>
              {formatCount(dueSources.length)} sources due
            </Badge>
          </>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <nav aria-label="Tools" className="space-y-2">
          {MODULES.map((module) => (
            <button
              key={module.id}
              type="button"
              onClick={() => setActiveModule(module.id)}
              aria-current={activeModule === module.id ? "true" : undefined}
              className={`w-full rounded-card border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 ${
                activeModule === module.id
                  ? "border-brand bg-brand-soft"
                  : "border-line bg-surface hover:border-line-strong hover:bg-surface-2"
              }`}
            >
              <div className="flex items-start gap-3">
                <div>
                  <span className="block text-sm font-semibold text-ink">{module.title}</span>
                  <span className="mt-1 block text-xs text-ink-2">{module.summary}</span>
                </div>
              </div>
            </button>
          ))}
        </nav>

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
                <p className="text-xs text-ink-2">
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
