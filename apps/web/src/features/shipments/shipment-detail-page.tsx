import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  Field,
  FileDropzone,
  PageHeader,
  QueryState,
  Select,
  Stepper,
  type Tone,
} from "@repo/ui";
import type {
  ChecklistItem,
  DiscrepancyItem,
  DocumentResponse,
  DocumentType,
  IncentiveEstimate,
} from "@repo/shared";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useLogout } from "../../lib/use-logout";

type Tab = "checklist" | "documents" | "report" | "expert";
type StepState = "done" | "active" | "available" | "locked";

const TAB_ORDER: Tab[] = ["checklist", "documents", "report", "expert"];
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const UPLOAD_ACCEPT = ".pdf,.jpg,.jpeg,.png,.webp,.xlsx,.xls";

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

const DOC_STATUS: Record<string, { tone: Tone; label: string }> = {
  pending: { tone: "warning", label: "Processing" },
  extracted: { tone: "success", label: "Done" },
  failed: { tone: "danger", label: "Failed" },
};

const RISK: Record<string, { tone: Tone; label: string }> = {
  low: { tone: "success", label: "Low risk" },
  medium: { tone: "warning", label: "Medium risk" },
  high: { tone: "warning", label: "High risk" },
  critical: { tone: "danger", label: "Critical risk" },
};

// match / check / mismatch labels for finding severity.
const SEVERITY: Record<string, { tone: Tone; label: string }> = {
  info: { tone: "info", label: "Note" },
  warn: { tone: "warning", label: "Check" },
  critical: { tone: "danger", label: "Mismatch" },
};

function severityOf(severity: string): { tone: Tone; label: string } {
  return SEVERITY[severity] ?? SEVERITY.info;
}

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

const formatInr = (n: number) => `INR ${n.toLocaleString("en-IN")}`;

// Sub-components

function ExtractedFieldsPanel({ doc }: { doc: DocumentResponse }) {
  const [open, setOpen] = useState(false);

  if (doc.upload_status === "pending" || doc.upload_status === "failed") return null;
  if (!doc.extracted_fields || Object.keys(doc.extracted_fields).length === 0) return null;

  const fields = Object.entries(doc.extracted_fields).filter(([k]) => k !== "_note");
  const note = doc.extracted_fields["_note"] as string | undefined;

  if (note) {
    return <p className="mt-2 text-sm text-ink-2">{note}</p>;
  }

  if (!fields.length) return null;

  return (
    <div className="mt-2">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="rounded-sm text-sm font-medium text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        {open ? "Hide" : "Show"} {fields.length} fields extracted
      </button>
      {open && (
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 rounded-panel border border-line bg-surface-2 px-3 py-2">
          {fields.map(([key, value]) => (
            <div key={key} className="flex flex-col">
              <dt className="text-xs text-ink-3">{FIELD_LABELS[key] ?? key}</dt>
              <dd className="text-sm text-ink">{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

function ChecklistSection({ title, items }: { title: string; items: ChecklistItem[] }) {
  if (!items.length) return null;
  return (
    <section className="mb-6">
      <h3 className="mb-3 text-sm font-semibold text-ink">{title}</h3>
      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li
            key={item.document_type}
            className="flex items-start gap-3 rounded-panel border border-line bg-surface px-4 py-3"
          >
            <Badge tone={item.required ? "info" : "neutral"} className="mt-0.5 shrink-0">
              {item.required ? "Required" : "Optional"}
            </Badge>
            <div>
              <p className="text-sm font-medium text-ink">{item.label}</p>
              <p className="mt-0.5 text-sm text-ink-2">{item.reason}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function FindingsTable({ items }: { items: DiscrepancyItem[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">Cross-document findings</caption>
        <thead>
          <tr className="bg-surface-2 text-left text-xs font-semibold text-ink-3">
            <th scope="col" className="px-5 py-2">
              Field
            </th>
            <th scope="col" className="px-5 py-2">
              Status
            </th>
            <th scope="col" className="hidden px-5 py-2 md:table-cell">
              Documents
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((d, i) => {
            const sev = severityOf(d.severity);
            return (
              <tr key={i} className="border-t border-line align-top">
                <td className="px-5 py-3">
                  <p className="font-medium capitalize text-ink">{d.field.replaceAll("_", " ")}</p>
                  <p className="text-ink-2">{d.message}</p>
                  <p className="mt-1 text-xs text-ink-3">
                    {d.document_a}: <span className="font-mono">{d.value_a}</span>
                    {d.document_b != null && (
                      <>
                        {" · "}
                        {d.document_b}: <span className="font-mono">{d.value_b ?? "-"}</span>
                      </>
                    )}
                  </p>
                  <p className="mt-1 text-xs text-ink-2">Fix: {d.suggested_fix}</p>
                </td>
                <td className="px-5 py-3">
                  <Badge tone={sev.tone}>{sev.label}</Badge>
                </td>
                <td className="hidden px-5 py-3 text-xs text-ink-3 md:table-cell">
                  {[d.document_a, d.document_b].filter(Boolean).join(", ")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function IncentiveCard({ e }: { e: IncentiveEstimate }) {
  return (
    <div className="rounded-panel border border-line bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="font-semibold text-ink">{e.scheme}</p>
        <Badge tone={e.eligible ? "success" : "neutral"}>
          {e.eligible ? "Eligible" : "Not eligible"}
        </Badge>
      </div>
      {e.eligible && e.estimated_amount != null && (
        <p className="mt-1 text-lg font-semibold text-ink">
          {formatInr(e.estimated_amount)}
          {e.rate_percent != null && (
            <span className="ml-2 text-sm font-normal text-ink-2">@ {e.rate_percent}%</span>
          )}
        </p>
      )}
      <p className="mt-1 text-sm text-ink-2">{e.notes}</p>
      {e.action_items.length > 0 && (
        <ul className="mt-2 list-inside list-disc text-sm text-ink-2">
          {e.action_items.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

const EXPERT_PLANS = [
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
];

// Page

export function ShipmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { session, token } = useAuth();
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
    mutationFn: (documentType: DocumentType) => api.generateDocument(id!, documentType, token!),
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

  const logoutMutation = useLogout();

  const s = shipmentQuery.data;
  const docs = docsQuery.data ?? [];
  const hasDocs = docs.length > 0;
  const report = reportQuery.data;

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <PageHeader
        title={s?.product_name ?? "Shipment"}
        breadcrumbs={[
          { label: "Shipments", href: "/shipments" },
          { label: s?.product_name ?? "Shipment" },
        ]}
        renderLink={(crumb, className) => (
          <Link to={crumb.href!} className={className}>
            {crumb.label}
          </Link>
        )}
        meta={
          s ? (
            <>
              <span>
                HSN <span className="font-mono">{s.hsn_code}</span>
              </span>
              <span>{s.destination_country}</span>
              <span>
                {s.incoterm} · {s.payment_term}
              </span>
              {s.fob_value ? (
                <span>
                  FOB {s.invoice_currency} {s.fob_value.toLocaleString("en-IN")}
                </span>
              ) : null}
              <Badge tone="neutral" className="capitalize">
                {s.shipment_mode} / {s.shipment_stage.replace("_", " ")}
              </Badge>
            </>
          ) : undefined
        }
      />

      {shipmentQuery.isError && (
        <Alert tone="danger" title="Could not load this shipment" className="mb-4">
          {userMessageForError(shipmentQuery.error)}
        </Alert>
      )}

      <Stepper
        className="mb-6"
        label="Shipment progress"
        current={tab}
        steps={STEPS.map((step) => ({
          id: step.key,
          label: step.label,
          disabled: getStepState(step.key, tab, hasDocs) === "locked",
          // A step that failed to load is not "done" just because the user moved past it.
          done:
            getStepState(step.key, tab, hasDocs) === "done" &&
            !(step.key === "checklist" && checklistQuery.isError),
        }))}
        onStepClick={(key) => setTab(key as Tab)}
      />

      {/* Checklist */}
      {tab === "checklist" && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>Document Checklist</CardTitle>
              <Badge tone="info">AI assist</Badge>
            </div>
            <CardDescription>
              AI-generated based on your shipment profile. Verify with your CHA.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <QueryState
              isLoading={checklistQuery.isLoading}
              isError={checklistQuery.isError}
              error={userMessageForError(checklistQuery.error)}
              onRetry={() => void checklistQuery.refetch()}
              isEmpty={
                Boolean(checklistQuery.data) &&
                checklistQuery.data!.required.length === 0 &&
                checklistQuery.data!.optional.length === 0 &&
                checklistQuery.data!.country_specific.length === 0 &&
                checklistQuery.data!.bank_payment.length === 0 &&
                checklistQuery.data!.incentive_refund.length === 0
              }
              empty={
                <EmptyState
                  title="No documents required"
                  description="The checklist came back empty for this profile."
                />
              }
            >
              {checklistQuery.data && (
                <>
                  <ChecklistSection
                    title="Required documents"
                    items={checklistQuery.data.required}
                  />
                  <ChecklistSection
                    title="Country-specific"
                    items={checklistQuery.data.country_specific}
                  />
                  <ChecklistSection
                    title="Bank & payment"
                    items={checklistQuery.data.bank_payment}
                  />
                  <ChecklistSection
                    title="Incentive & refund"
                    items={checklistQuery.data.incentive_refund}
                  />
                  <ChecklistSection title="Optional" items={checklistQuery.data.optional} />
                  <p className="mt-4 text-xs text-ink-3">{checklistQuery.data.disclaimer}</p>
                  <Button className="mt-4" onClick={() => setTab("documents")}>
                    Upload documents
                  </Button>
                </>
              )}
            </QueryState>
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
                <Alert tone="danger" title="Generation failed" className="w-full">
                  {userMessageForError(generateMutation.error)}
                </Alert>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Upload Document</CardTitle>
              <CardDescription>PDF, JPEG, PNG, or Excel. Max 10 MB per file.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Field label="Document type" className="max-w-sm">
                <Select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value as DocumentType)}
                >
                  {Object.entries(DOCUMENT_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="File">
                {(p) => (
                  <FileDropzone
                    id={p.id}
                    aria-describedby={p["aria-describedby"]}
                    accept={UPLOAD_ACCEPT}
                    maxBytes={MAX_UPLOAD_BYTES}
                    file={uploadFile}
                    onFileChange={setUploadFile}
                    disabled={uploadMutation.isPending}
                  />
                )}
              </Field>
              <div>
                <Button
                  disabled={!uploadFile}
                  loading={uploadMutation.isPending}
                  onClick={() => uploadMutation.mutate()}
                >
                  {uploadMutation.isPending ? "Uploading..." : "Upload"}
                </Button>
              </div>
              {uploadMutation.isError && (
                <Alert tone="danger" title="Upload failed">
                  {userMessageForError(uploadMutation.error)}
                </Alert>
              )}
              {uploadMutation.isSuccess && (
                <Alert tone="success" title="Document uploaded successfully." />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Uploaded documents</CardTitle>
            </CardHeader>
            <CardContent>
              <QueryState
                isLoading={docsQuery.isLoading}
                isError={docsQuery.isError}
                error={userMessageForError(docsQuery.error)}
                onRetry={() => void docsQuery.refetch()}
                isEmpty={!hasDocs}
                empty={
                  <EmptyState
                    title="No documents uploaded yet"
                    description="Upload a file or generate a draft above."
                  />
                }
              >
                <ul className="flex flex-col gap-2">
                  {docs.map((doc) => {
                    const status = DOC_STATUS[doc.upload_status];
                    return (
                      <li
                        key={doc.id}
                        className="rounded-panel border border-line bg-surface px-4 py-3"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-ink">
                              {DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type}
                            </p>
                            <p className="truncate text-xs text-ink-3">
                              {doc.file_name}
                              {doc.file_size_bytes
                                ? ` / ${(doc.file_size_bytes / 1024).toFixed(0)} KB`
                                : ""}
                            </p>
                          </div>
                          {status && (
                            <div className="flex shrink-0 items-center gap-3">
                              <Badge tone={status.tone}>{status.label}</Badge>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  api.downloadDocument(id!, doc.id, doc.file_name, token!)
                                }
                              >
                                Download
                              </Button>
                            </div>
                          )}
                        </div>
                        <ExtractedFieldsPanel doc={doc} />
                      </li>
                    );
                  })}
                </ul>
              </QueryState>
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
            <Alert tone="warning" title="Upload at least one document before running verification.">
              <Button
                size="sm"
                variant="secondary"
                className="mt-2"
                onClick={() => setTab("documents")}
              >
                Upload docs
              </Button>
            </Alert>
          )}

          {hasDocs && (
            <Card>
              <CardHeader>
                <CardTitle>Deterministic reconciliation</CardTitle>
                <CardDescription>
                  Checks required documents and extracted cross-document values without asking AI to
                  invent rules or rates.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button
                  loading={reconciliationMutation.isPending}
                  onClick={() => reconciliationMutation.mutate()}
                >
                  {reconciliationMutation.isPending ? "Reconciling..." : "Run reconciliation"}
                </Button>
                {reconciliationMutation.isError && (
                  <Alert tone="danger" title="Reconciliation failed">
                    {userMessageForError(reconciliationMutation.error)}
                  </Alert>
                )}
                {reconciliationMutation.data ? (
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-ink">
                      {reconciliationMutation.data.discrepancies.length} findings / potential{" "}
                      {formatInr(reconciliationMutation.data.potential_amount)}
                    </p>
                    <ul className="space-y-2">
                      {reconciliationMutation.data.discrepancies.map((item) => {
                        const sev = severityOf(item.severity);
                        return (
                          <li
                            key={item.id}
                            className="flex items-start justify-between gap-3 rounded-panel border border-line bg-surface p-3"
                          >
                            <div>
                              <p className="text-sm text-ink">{item.message}</p>
                              <p className="mt-1 text-xs capitalize text-ink-3">
                                {item.type.replaceAll("_", " ")}
                              </p>
                            </div>
                            <Badge tone={sev.tone}>{sev.label}</Badge>
                          </li>
                        );
                      })}
                    </ul>
                    <p className="text-xs text-ink-3">{reconciliationMutation.data.disclaimer}</p>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          )}

          {hasDocs && reportQuery.isLoading && (
            <p className="text-sm text-ink-2">Running AI verification...</p>
          )}
          {hasDocs && (
            <QueryState
              isLoading={reportQuery.isLoading}
              isError={reportQuery.isError}
              error={userMessageForError(reportQuery.error)}
              onRetry={() => void reportQuery.refetch()}
            >
              {report && (
                <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
                  <div className="flex min-w-0 flex-col gap-4">
                    {report.missing_documents.length > 0 && (
                      <Alert tone="danger" title="Missing documents">
                        <ul className="list-inside list-disc">
                          {report.missing_documents.map((d, i) => (
                            <li key={i}>{d}</li>
                          ))}
                        </ul>
                      </Alert>
                    )}

                    {report.discrepancies.length > 0 && (
                      <Card>
                        <CardHeader>
                          <div className="flex items-center gap-2">
                            <CardTitle>Cross-document findings</CardTitle>
                            <Badge tone="info">AI assist</Badge>
                          </div>
                        </CardHeader>
                        <FindingsTable items={report.discrepancies} />
                      </Card>
                    )}

                    <Card>
                      <CardHeader>
                        <div className="flex items-center gap-2">
                          <CardTitle>Incentive estimates</CardTitle>
                          <Badge tone="info">AI assist</Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="grid gap-3 md:grid-cols-2">
                        {report.incentive_estimates.map((e, i) => (
                          <IncentiveCard key={i} e={e} />
                        ))}
                      </CardContent>
                    </Card>

                    {(report.ebrc_gst_reminders.length > 0 ||
                      report.recommendations.length > 0) && (
                      <Card>
                        <CardHeader>
                          <CardTitle>Action items</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <ul className="flex flex-col gap-2">
                            {report.recommendations.map((rec, i) => (
                              <li key={i} className="flex items-start gap-2 text-sm text-ink">
                                <Badge tone="info" className="shrink-0">
                                  Action
                                </Badge>
                                {rec}
                              </li>
                            ))}
                            {report.ebrc_gst_reminders.map((rem, i) => (
                              <li key={i} className="flex items-start gap-2 text-sm text-ink">
                                <Badge tone="warning" className="shrink-0">
                                  Reminder
                                </Badge>
                                {rem}
                              </li>
                            ))}
                          </ul>
                        </CardContent>
                      </Card>
                    )}

                    <p className="text-xs text-ink-3">{report.disclaimer}</p>
                    <div>
                      <Button onClick={() => setTab("expert")}>Get expert review</Button>
                    </div>
                  </div>

                  <aside className="min-w-0">
                    <Card className="p-5">
                      <h2 className="text-base font-semibold text-ink">Finance readiness</h2>
                      <p className="mt-3 text-4xl font-bold leading-none text-ink">
                        {report.finance_readiness_score}
                        <span className="text-base font-normal text-ink-3">/100</span>
                      </p>
                      <div
                        className="my-3 h-1.5 rounded-full bg-surface-2"
                        role="progressbar"
                        aria-label="Finance readiness"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={report.finance_readiness_score}
                      >
                        <div
                          className={`h-full rounded-full ${
                            report.finance_readiness_score >= 80
                              ? "bg-success-fg"
                              : report.finance_readiness_score >= 50
                                ? "bg-warning-fg"
                                : "bg-danger-fg"
                          }`}
                          style={{
                            width: `${Math.min(100, Math.max(0, report.finance_readiness_score))}%`,
                          }}
                        />
                      </div>
                      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
                        <dt className="text-ink-3">Overall risk</dt>
                        <dd className="text-right">
                          <Badge tone={RISK[report.overall_risk]?.tone ?? "neutral"}>
                            {RISK[report.overall_risk]?.label ?? report.overall_risk}
                          </Badge>
                        </dd>
                        <dt className="text-ink-3">Findings</dt>
                        <dd className="text-right text-ink">
                          {report.discrepancies.length.toLocaleString("en-IN")}
                        </dd>
                        <dt className="text-ink-3">Missing docs</dt>
                        <dd className="text-right text-ink">
                          {report.missing_documents.length.toLocaleString("en-IN")}
                        </dd>
                      </dl>
                    </Card>
                  </aside>
                </div>
              )}
            </QueryState>
          )}
        </div>
      )}

      {/* Expert review */}
      {tab === "expert" && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle>Expert Review</CardTitle>
              <Badge tone="neutral">Coming soon</Badge>
            </div>
            <CardDescription>
              Have a licensed export documentation expert review this shipment audit report.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <div className="grid gap-4 md:grid-cols-3">
              {EXPERT_PLANS.map((plan) => (
                <div
                  key={plan.tier}
                  className={`flex flex-col gap-3 rounded-card border p-5 ${
                    plan.highlight ? "border-info-border bg-brand-soft" : "border-line bg-surface"
                  }`}
                >
                  <h3 className="text-sm font-semibold text-ink-2">{plan.tier}</h3>
                  <p className="text-2xl font-semibold text-ink">{plan.price}</p>
                  <p className="text-sm text-ink-2">{plan.desc}</p>
                  <Button
                    variant={plan.highlight ? "primary" : "secondary"}
                    className="mt-auto"
                    disabled
                  >
                    Request review
                  </Button>
                </div>
              ))}
            </div>
            <div className="rounded-panel border border-line bg-surface-2 px-5 py-4 text-sm text-ink-2">
              <p className="mb-1 font-medium text-ink">What experts check</p>
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
