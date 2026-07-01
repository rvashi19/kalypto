import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { Button, Card, CardContent, CardHeader, CardTitle, CardDescription } from "@repo/ui";
import type {
  ChecklistItem,
  DiscrepancyItem,
  DocumentResponse,
  DocumentType,
  IncentiveEstimate,
} from "@repo/shared";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import {
  AiBadge,
  ComingSoonBadge,
  DOC_STATUS_CFG,
  RISK_CFG,
  SEVERITY_CFG,
  selectCls,
} from "../../lib/ui";

type Tab = "checklist" | "documents" | "report" | "expert";
type StepState = "done" | "active" | "available" | "locked";

const TAB_ORDER: Tab[] = ["checklist", "documents", "report", "expert"];

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  proforma_invoice: "Proforma Invoice",
  commercial_invoice: "Commercial Invoice",
  packing_list: "Packing List",
  purchase_order: "Purchase Order",
  bl_awb: "BL / AWB",
  shipping_bill: "Shipping Bill",
  certificate_of_origin: "Certificate of Origin",
  insurance: "Insurance",
  inspection_certificate: "Inspection Certificate",
  phytosanitary_certificate: "Phytosanitary Certificate",
  fumigation_certificate: "Fumigation Certificate",
  ebrc: "eBRC",
  other: "Other",
};

const FIELD_LABELS: Record<string, string> = {
  document_number: "Doc No.",
  invoice_number: "Invoice No.",
  document_date: "Date",
  buyer_name: "Buyer",
  seller_name: "Seller",
  hsn_code: "HSN",
  product_description: "Product",
  quantity: "Qty",
  unit_of_measure: "UOM",
  net_weight_kg: "Net Wt (kg)",
  gross_weight_kg: "Gross Wt (kg)",
  fob_value: "FOB Value",
  cif_value: "CIF Value",
  currency: "Currency",
  incoterm: "Incoterm",
  payment_term: "Payment Term",
  port_of_loading: "POL",
  port_of_discharge: "POD",
  vessel_flight_no: "Vessel/Flight",
  bl_awb_number: "BL/AWB No.",
  shipping_bill_no: "Shipping Bill",
  igst_amount: "IGST Amount",
  gstin: "GSTIN",
  iec_code: "IEC Code",
  ad_code: "AD Code",
  marks_and_numbers: "Marks & Nos.",
};

// Stepper

const STEPS: { key: Tab; label: string }[] = [
  { key: "checklist", label: "Checklist" },
  { key: "documents", label: "Documents" },
  { key: "report", label: "Verify" },
  { key: "expert", label: "Expert" },
];

function getStepState(key: Tab, current: Tab, hasDocs: boolean): StepState {
  if (key === "expert") return "locked";
  const idx = TAB_ORDER.indexOf(key);
  const curIdx = TAB_ORDER.indexOf(current);
  if (idx < curIdx) return "done";
  if (idx === curIdx) return "active";
  if (key === "report" && !hasDocs) return "locked";
  return "available";
}

function StepBubble({
  n,
  label,
  state,
  onClick,
}: {
  n: number;
  label: string;
  state: StepState;
  onClick?: () => void;
}) {
  const circleCls: Record<StepState, string> = {
    done: "bg-cyan-300 text-slate-950",
    active: "border-2 border-cyan-300 bg-cyan-300/10 text-cyan-100",
    available: "border-2 border-slate-700 bg-slate-900 text-slate-400 hover:border-cyan-300/50",
    locked: "border-2 border-slate-800 bg-slate-950 text-slate-600",
  };
  const labelCls: Record<StepState, string> = {
    done: "text-cyan-200",
    active: "font-semibold text-slate-100",
    available: "text-slate-400",
    locked: "text-slate-600",
  };
  const canClick = state !== "locked" && Boolean(onClick);

  return (
    <button
      onClick={canClick ? onClick : undefined}
      disabled={!canClick}
      className="flex flex-col items-center gap-1.5 disabled:cursor-default"
      aria-current={state === "active" ? "step" : undefined}
    >
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-colors ${circleCls[state]}`}
      >
        {state === "done" ? "OK" : n}
      </span>
      <span
        className={`whitespace-nowrap text-[10px] font-medium uppercase tracking-wide transition-colors ${labelCls[state]}`}
      >
        {label}
      </span>
    </button>
  );
}

function Stepper({
  current,
  hasDocs,
  onSelect,
}: {
  current: Tab;
  hasDocs: boolean;
  onSelect: (tab: Tab) => void;
}) {
  return (
    <div className="mb-6 overflow-x-auto">
      <div className="flex min-w-max items-start">
        {STEPS.flatMap((step, i) => {
          const bubble = (
            <StepBubble
              key={step.key}
              n={i + 1}
              label={step.label}
              state={getStepState(step.key, current, hasDocs)}
              onClick={() => onSelect(step.key)}
            />
          );
          if (i < STEPS.length - 1) {
            return [
              bubble,
              <div key={`sep-${i}`} className="mt-4 h-px w-8 flex-1 bg-slate-800 sm:w-12 md:w-16" aria-hidden="true" />,
            ];
          }
          return [bubble];
        })}
      </div>
    </div>
  );
}

// Sub-components

function ExtractedFieldsPanel({ doc }: { doc: DocumentResponse }) {
  const [open, setOpen] = useState(false);
  const cfg = DOC_STATUS_CFG[doc.upload_status as keyof typeof DOC_STATUS_CFG];

  if (doc.upload_status === "pending") {
    return (
      <div className={`mt-1 flex items-center gap-1.5 text-xs ${cfg?.cls ?? "text-amber-400"}`}>
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-current" aria-hidden="true" />
        {cfg?.label ?? "Processing"}
      </div>
    );
  }

  if (doc.upload_status === "failed") {
    return (
      <p className={`mt-1 flex items-center gap-1 text-xs ${cfg?.cls ?? "text-rose-400"}`}>
        <span aria-hidden="true">{cfg?.icon}</span>
        {cfg?.label ?? "Failed"}
      </p>
    );
  }

  if (!doc.extracted_fields || Object.keys(doc.extracted_fields).length === 0) return null;

  const fields = Object.entries(doc.extracted_fields).filter(([k]) => k !== "_note");
  const note = doc.extracted_fields["_note"] as string | undefined;

  if (note) {
    return (
      <p className={`mt-1 text-xs ${cfg?.cls ?? "text-emerald-400"}`}>
        <span aria-hidden="true">{cfg?.icon}</span> {note}
      </p>
    );
  }

  if (!fields.length) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200"
      >
        {open ? "Hide" : "Show"} {fields.length} fields extracted
      </button>
      {open && (
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 rounded-lg border border-white/5 bg-slate-900/60 px-3 py-2">
          {fields.map(([key, value]) => (
            <div key={key} className="flex flex-col">
              <span className="text-xs text-slate-500">{FIELD_LABELS[key] ?? key}</span>
              <span className="text-xs text-slate-200">{String(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ChecklistSection({
  title,
  items,
  color,
}: {
  title: string;
  items: ChecklistItem[];
  color: string;
}) {
  if (!items.length) return null;
  return (
    <div className="mb-6">
      <h4 className={`mb-3 text-xs font-bold uppercase tracking-widest ${color}`}>{title}</h4>
      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <div
            key={item.document_type}
            className="flex items-start gap-3 rounded-xl border border-white/8 bg-slate-950/60 px-4 py-3"
          >
            <span
              className={`mt-0.5 text-xs font-semibold uppercase tracking-wide ${item.required ? "text-cyan-200" : "text-slate-500"}`}
              aria-hidden="true"
            >
              {item.required ? "Required" : "Optional"}
            </span>
            <div>
              <p className="text-sm font-medium text-slate-100">{item.label}</p>
              <p className="mt-0.5 text-xs text-slate-500">{item.reason}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DiscrepancyCard({ d }: { d: DiscrepancyItem }) {
  const cfg = SEVERITY_CFG[d.severity as keyof typeof SEVERITY_CFG] ?? SEVERITY_CFG.info;
  return (
    <div className={`rounded-xl border p-4 ${cfg.cls}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold capitalize">{d.field.replaceAll("_", " ")}</p>
        <span className="flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs capitalize">
          <span aria-hidden="true">{cfg.icon}</span> {d.severity}
        </span>
      </div>
      <p className="mt-2 text-xs opacity-90">{d.message}</p>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs opacity-75">
        <div>
          <span className="font-medium">{d.document_a}:</span> {d.value_a}
        </div>
        {d.document_b != null && (
          <div>
            <span className="font-medium">{d.document_b}:</span> {d.value_b ?? "-"}
          </div>
        )}
      </div>
      <p className="mt-2 text-xs italic opacity-75">Fix: {d.suggested_fix}</p>
    </div>
  );
}

function IncentiveCard({ e }: { e: IncentiveEstimate }) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        e.eligible
          ? "border-emerald-500/20 bg-emerald-500/8"
          : "border-white/8 bg-slate-950/60"
      }`}
    >
      <div className="flex items-center justify-between">
        <p className="font-semibold text-slate-100">{e.scheme}</p>
        <span className={`text-xs font-bold ${e.eligible ? "text-emerald-400" : "text-slate-500"}`}>
          {e.eligible ? "Eligible" : "Not eligible"}
        </span>
      </div>
      {e.eligible && e.estimated_amount != null && (
        <p className="mt-1 text-lg font-bold text-emerald-400">
          INR {e.estimated_amount.toLocaleString("en-IN")}
          {e.rate_percent != null && (
            <span className="ml-2 text-sm font-normal text-emerald-600">@ {e.rate_percent}%</span>
          )}
        </p>
      )}
      <p className="mt-1 text-xs text-slate-400">{e.notes}</p>
      {e.action_items.length > 0 && (
        <ul className="mt-2 list-inside list-disc text-xs text-slate-400">
          {e.action_items.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Page

export function ShipmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { session, token, setSession } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("checklist");
  const [uploadType, setUploadType] = useState<DocumentType>("commercial_invoice");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const shipmentQuery = useQuery({
    queryKey: ["shipment", id, token],
    queryFn: () => api.getShipment(id!, token!),
    enabled: Boolean(id && token),
  });

  const checklistQuery = useQuery({
    queryKey: ["checklist", id, token],
    queryFn: () => api.getChecklist(id!, token!),
    enabled: Boolean(id && token && tab === "checklist"),
  });

  // Always enabled so stepper can gate the Verify step
  const docsQuery = useQuery({
    queryKey: ["documents", id, token],
    queryFn: () => api.listDocuments(id!, token!),
    enabled: Boolean(id && token),
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.upload_status === "pending") ? 3000 : false,
  });

  const reportQuery = useQuery({
    queryKey: ["report", id, token],
    queryFn: () => api.verifyShipment(id!, token!),
    enabled: Boolean(id && token && tab === "report"),
  });

  const uploadMutation = useMutation({
    mutationFn: () => api.uploadDocument(id!, uploadType, uploadFile!, token!),
    onSuccess: () => {
      setUploadFile(null);
      qc.invalidateQueries({ queryKey: ["documents", id] });
    },
  });

  const generateMutation = useMutation({
    mutationFn: (documentType: DocumentType) =>
      api.generateDocument(id!, documentType, token!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents", id] });
    },
  });

  const reconciliationMutation = useMutation({
    mutationFn: () => api.reconcileShipment(id!, token!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discrepancy-dashboard"] });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });

  const s = shipmentQuery.data;
  const hasDocs = (docsQuery.data?.length ?? 0) > 0;

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <button
        onClick={() => navigate("/shipments")}
        className="mb-3 text-sm text-slate-500 hover:text-slate-300"
      >
        Back to shipments
      </button>

      {s && (
        <div className="mb-5 rounded-xl border border-white/8 bg-slate-900/70 px-5 py-4 backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold text-slate-50">{s.product_name}</h2>
              <p className="text-sm text-slate-400">
                HSN {s.hsn_code} / {s.destination_country} / {s.incoterm} / {s.payment_term}
              </p>
            </div>
            <span className="rounded-md border border-white/10 px-3 py-1 text-xs capitalize text-slate-400">
              {s.shipment_mode} / {s.shipment_stage.replace("_", " ")}
            </span>
          </div>
          {s.fob_value && (
            <p className="mt-2 text-sm text-slate-500">
              FOB {s.invoice_currency} {s.fob_value.toLocaleString()}
            </p>
          )}
        </div>
      )}

      <Stepper current={tab} hasDocs={hasDocs} onSelect={setTab} />

      {/* Checklist */}
      {tab === "checklist" && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>Document Checklist</CardTitle>
              <AiBadge />
            </div>
            <CardDescription>
              AI-generated based on your shipment profile. Verify with your CHA.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {checklistQuery.isLoading && (
              <p className="text-sm text-slate-400">Generating checklist...</p>
            )}
            {checklistQuery.isError && (
              <p className="text-sm text-rose-400">
                {checklistQuery.error instanceof Error
                  ? checklistQuery.error.message
                  : "Error loading checklist."}
              </p>
            )}
            {checklistQuery.data && (
              <>
                <ChecklistSection
                  title="Required documents"
                  items={checklistQuery.data.required}
                  color="text-cyan-300"
                />
                <ChecklistSection
                  title="Country-specific"
                  items={checklistQuery.data.country_specific}
                  color="text-violet-400"
                />
                <ChecklistSection
                  title="Bank & payment"
                  items={checklistQuery.data.bank_payment}
                  color="text-amber-400"
                />
                <ChecklistSection
                  title="Incentive & refund"
                  items={checklistQuery.data.incentive_refund}
                  color="text-emerald-400"
                />
                <ChecklistSection
                  title="Optional"
                  items={checklistQuery.data.optional}
                  color="text-slate-400"
                />
                <p className="mt-4 text-xs text-slate-600">{checklistQuery.data.disclaimer}</p>
                <Button className="mt-4" onClick={() => setTab("documents")}>
                  Upload documents
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Documents */}
      {tab === "documents" && (
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Generate export documents</CardTitle>
              <CardDescription>
                Create editable-draft PDFs from the shipment profile, then review and sign them.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {(
                [
                  ["proforma_invoice", "Generate proforma invoice"],
                  ["commercial_invoice", "Generate commercial invoice"],
                  ["packing_list", "Generate packing list"],
                ] as Array<[DocumentType, string]>
              ).map(([documentType, label]) => (
                <Button
                  key={documentType}
                  variant="secondary"
                  disabled={generateMutation.isPending}
                  onClick={() => generateMutation.mutate(documentType)}
                >
                  {label}
                </Button>
              ))}
              {generateMutation.isError ? (
                <p className="w-full text-sm text-rose-400">
                  {generateMutation.error instanceof Error
                    ? generateMutation.error.message
                    : "Document generation failed."}
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Upload Document</CardTitle>
              <CardDescription>PDF, JPEG, PNG, or Excel. Max 10 MB per file.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 md:flex-row md:items-end">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium uppercase tracking-wider text-slate-400">
                  Document type
                </label>
                <select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value as DocumentType)}
                  className={selectCls}
                >
                  {Object.entries(DOCUMENT_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium uppercase tracking-wider text-slate-400">
                  File
                </label>
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.webp,.xlsx,.xls"
                  onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                  className="text-sm text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-xs file:text-slate-300 hover:file:bg-slate-700"
                />
              </div>
              <Button
                disabled={!uploadFile || uploadMutation.isPending}
                onClick={() => uploadMutation.mutate()}
              >
                {uploadMutation.isPending ? "Uploading..." : "Upload"}
              </Button>
            </CardContent>
            {uploadMutation.isError && (
              <div className="mx-6 mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/8 px-3 py-2 text-sm text-rose-300">
                <span aria-hidden="true">!</span>
                {uploadMutation.error instanceof Error
                  ? uploadMutation.error.message
                  : "Upload failed."}
              </div>
            )}
            {uploadMutation.isSuccess && (
              <div className="mx-6 mb-4 flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/8 px-3 py-2 text-sm text-emerald-300">
                <span aria-hidden="true">OK</span> Document uploaded successfully.
              </div>
            )}
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Uploaded documents</CardTitle>
            </CardHeader>
            <CardContent>
              {docsQuery.isLoading && <p className="text-sm text-slate-400">Loading...</p>}
              {!docsQuery.isLoading && docsQuery.data?.length === 0 && (
                <p className="text-sm text-slate-500">No documents uploaded yet.</p>
              )}
              <div className="flex flex-col gap-2">
                {docsQuery.data?.map((doc) => {
                  const statusCfg =
                    DOC_STATUS_CFG[doc.upload_status as keyof typeof DOC_STATUS_CFG];
                  return (
                    <div
                      key={doc.id}
                      className="rounded-xl border border-white/8 bg-slate-950/60 px-4 py-3"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-slate-100">
                            {DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type}
                          </p>
                          <p className="text-xs text-slate-500">
                            {doc.file_name}
                            {doc.file_size_bytes
                              ? ` / ${(doc.file_size_bytes / 1024).toFixed(0)} KB`
                              : ""}
                          </p>
                        </div>
                        {statusCfg && (
                          <div className="flex items-center gap-3">
                            <span className={`flex items-center gap-1 text-xs ${statusCfg.cls}`}>
                              <span aria-hidden="true">{statusCfg.icon}</span>
                              {statusCfg.label}
                            </span>
                            <button
                              className="text-xs font-medium text-cyan-300 hover:text-cyan-200"
                              onClick={() =>
                                api.downloadDocument(id!, doc.id, doc.file_name, token!)
                              }
                            >
                              Download
                            </button>
                          </div>
                        )}
                      </div>
                      <ExtractedFieldsPanel doc={doc} />
                    </div>
                  );
                })}
              </div>
              {hasDocs && (
                <Button className="mt-4" onClick={() => setTab("report")}>
                  Run verification
                </Button>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Report */}
      {tab === "report" && (
        <div className="flex flex-col gap-4">
          {!hasDocs && (
            <div className="flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/8 px-5 py-4 text-sm text-amber-300">
              <span aria-hidden="true">!</span>
              Upload at least one document before running verification.
              <Button size="sm" variant="secondary" onClick={() => setTab("documents")}>
                Upload docs
              </Button>
            </div>
          )}
          {hasDocs ? (
            <Card>
              <CardHeader>
                <CardTitle>Deterministic reconciliation</CardTitle>
                <CardDescription>
                  Checks required documents and extracted cross-document values without asking AI
                  to invent rules or rates.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  disabled={reconciliationMutation.isPending}
                  onClick={() => reconciliationMutation.mutate()}
                >
                  {reconciliationMutation.isPending
                    ? "Reconciling..."
                    : "Run reconciliation"}
                </Button>
                {reconciliationMutation.data ? (
                  <div className="mt-4 space-y-2">
                    <p className="text-sm font-medium text-slate-200">
                      {reconciliationMutation.data.discrepancies.length} findings / potential INR{" "}
                      {reconciliationMutation.data.potential_amount.toLocaleString("en-IN")}
                    </p>
                    {reconciliationMutation.data.discrepancies.map((item) => (
                      <div
                        className="rounded-lg border border-white/8 bg-slate-950/50 p-3"
                        key={item.id}
                      >
                        <p className="text-sm text-slate-200">{item.message}</p>
                        <p className="mt-1 text-xs capitalize text-slate-500">
                          {item.severity} / {item.type.replaceAll("_", " ")}
                        </p>
                      </div>
                    ))}
                    <p className="text-xs text-slate-600">
                      {reconciliationMutation.data.disclaimer}
                    </p>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ) : null}
          {hasDocs && reportQuery.isLoading && (
            <Card>
              <CardContent className="py-8 text-center text-sm text-slate-400">
                Running AI verification...
              </CardContent>
            </Card>
          )}
          {hasDocs && reportQuery.isError && (
            <div className="flex items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/8 px-4 py-3 text-sm text-rose-300">
              <span aria-hidden="true">!</span>
              {reportQuery.error instanceof Error
                ? reportQuery.error.message
                : "Verification failed."}
            </div>
          )}
          {hasDocs &&
            reportQuery.data &&
            (() => {
              const r = reportQuery.data;
              const risk =
                RISK_CFG[r.overall_risk as keyof typeof RISK_CFG];
              return (
                <>
                  <div className="flex flex-wrap items-center gap-4 rounded-xl border border-white/8 bg-slate-900/70 px-5 py-4">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Overall risk
                      </p>
                      <span
                        className={`mt-1.5 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-bold ${risk?.cls ?? "border-white/10 text-slate-300"}`}
                      >
                        <span aria-hidden="true">{risk?.icon}</span>
                        {risk?.label ?? r.overall_risk}
                      </span>
                    </div>
                    <div className="ml-auto text-right">
                      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Finance readiness
                      </p>
                      <p className="mt-1 text-2xl font-bold text-slate-100">
                        {r.finance_readiness_score}
                        <span className="text-sm text-slate-500">/100</span>
                      </p>
                    </div>
                  </div>

                  {r.missing_documents.length > 0 && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-rose-400">Missing documents</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ul className="list-inside list-disc space-y-1 text-sm text-slate-300">
                          {r.missing_documents.map((d, i) => (
                            <li key={i}>{d}</li>
                          ))}
                        </ul>
                      </CardContent>
                    </Card>
                  )}

                  {r.discrepancies.length > 0 && (
                    <Card>
                      <CardHeader>
                        <div className="flex items-center gap-2">
                          <CardTitle>Discrepancies</CardTitle>
                          <AiBadge />
                        </div>
                      </CardHeader>
                      <CardContent className="flex flex-col gap-3">
                        {r.discrepancies.map((d, i) => (
                          <DiscrepancyCard key={i} d={d} />
                        ))}
                      </CardContent>
                    </Card>
                  )}

                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-2">
                        <CardTitle>Incentive estimates</CardTitle>
                        <AiBadge />
                      </div>
                    </CardHeader>
                    <CardContent className="grid gap-3 md:grid-cols-2">
                      {r.incentive_estimates.map((e, i) => (
                        <IncentiveCard key={i} e={e} />
                      ))}
                    </CardContent>
                  </Card>

                  {(r.ebrc_gst_reminders.length > 0 || r.recommendations.length > 0) && (
                    <Card>
                      <CardHeader>
                        <CardTitle>Action items</CardTitle>
                      </CardHeader>
                      <CardContent className="flex flex-col gap-2">
                        {r.recommendations.map((rec, i) => (
                          <div key={i} className="flex gap-2 text-sm text-slate-300">
                            <span className="mt-0.5 text-cyan-300" aria-hidden="true">
                              Action
                            </span>
                            {rec}
                          </div>
                        ))}
                        {r.ebrc_gst_reminders.map((rem, i) => (
                          <div key={i} className="flex gap-2 text-sm text-amber-300">
                            <span className="mt-0.5" aria-hidden="true">
                              Alert
                            </span>
                            {rem}
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  )}

                  <p className="text-xs text-slate-600">{r.disclaimer}</p>
                  <Button onClick={() => setTab("expert")}>Get expert review</Button>
                </>
              );
            })()}
        </div>
      )}

      {/* Expert review */}
      {tab === "expert" && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>Expert Review</CardTitle>
              <ComingSoonBadge />
            </div>
            <CardDescription>
              Have a licensed export documentation expert review this shipment audit report.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <div className="grid gap-4 md:grid-cols-3">
              {[
                {
                  tier: "Basic AI check",
                  price: "INR 999",
                  desc: "AI report with priority support response within 24 hrs.",
                  highlight: false,
                },
                {
                  tier: "Expert audit",
                  price: "INR 4,999",
                  desc: "Licensed CHA reviews your documents and report. Written feedback within 48 hrs.",
                  highlight: true,
                },
                {
                  tier: "Full advisory",
                  price: "INR 9,999",
                  desc: "CHA + CA review. Includes RoDTEP claim filing guidance and eBRC tracking.",
                  highlight: false,
                },
              ].map((plan) => (
                <div
                  key={plan.tier}
                  className={`flex flex-col gap-3 rounded-xl border p-5 ${
                    plan.highlight
                      ? "border-cyan-300/20 bg-cyan-300/10"
                      : "border-white/10 bg-slate-950/60"
                  }`}
                >
                  <p className="text-xs font-bold uppercase tracking-widest text-slate-400">
                    {plan.tier}
                  </p>
                  <p
                    className={`text-2xl font-bold ${
                      plan.highlight ? "text-cyan-100" : "text-slate-100"
                    }`}
                  >
                    {plan.price}
                  </p>
                  <p className="text-sm text-slate-400">{plan.desc}</p>
                  <Button
                    variant={plan.highlight ? "default" : "secondary"}
                    className="mt-auto"
                    disabled
                  >
                    Request review
                  </Button>
                </div>
              ))}
            </div>
            <div className="rounded-xl border border-white/8 bg-slate-950/60 px-5 py-4 text-sm text-slate-400">
              <p className="mb-1 font-medium text-slate-300">What experts check</p>
              <ul className="list-inside list-disc space-y-1">
                <li>All document field mismatches</li>
                <li>RoDTEP / Duty Drawback claim eligibility and filing</li>
                <li>eBRC realization status and DGFT compliance</li>
                <li>GST refund eligibility (LUT / IGST route)</li>
                <li>Country-specific certificate requirements</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      )}
    </DashboardShell>
  );
}
