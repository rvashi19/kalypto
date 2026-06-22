import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { Button, Card, CardContent, CardHeader, CardTitle, CardDescription } from "@repo/ui";
import type { ChecklistItem, DiscrepancyItem, DocumentResponse, DocumentType, IncentiveEstimate } from "@repo/shared";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

type Tab = "checklist" | "documents" | "report" | "expert";

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

const SEVERITY_STYLES: Record<string, string> = {
  info: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  warn: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  critical: "border-rose-500/30 bg-rose-500/10 text-rose-300",
};

const RISK_STYLES: Record<string, string> = {
  low: "bg-green-500/15 text-green-300 border-green-500/20",
  medium: "bg-amber-500/15 text-amber-300 border-amber-500/20",
  high: "bg-orange-500/15 text-orange-300 border-orange-500/20",
  critical: "bg-rose-500/15 text-rose-300 border-rose-500/20",
};

const FIELD_LABELS: Record<string, string> = {
  document_number: "Doc No.",
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
  marks_and_numbers: "Marks & Nos.",
};

function ExtractedFieldsPanel({ doc }: { doc: DocumentResponse }) {
  const [open, setOpen] = useState(false);

  if (doc.upload_status === "pending") {
    return (
      <div className="mt-1 flex items-center gap-1.5 text-xs text-amber-400">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-400" />
        Extracting fields…
      </div>
    );
  }

  if (doc.upload_status === "failed") {
    return <p className="mt-1 text-xs text-rose-400">Extraction failed</p>;
  }

  if (!doc.extracted_fields || Object.keys(doc.extracted_fields).length === 0) return null;

  const fields = Object.entries(doc.extracted_fields).filter(([k]) => k !== "_note");
  const note = doc.extracted_fields["_note"] as string | undefined;

  if (note) {
    return <p className="mt-1 text-xs text-slate-500">{note}</p>;
  }

  if (!fields.length) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300"
      >
        {open ? "▾" : "▸"} {fields.length} fields extracted
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

function ChecklistSection({ title, items, color }: { title: string; items: ChecklistItem[]; color: string }) {
  if (!items.length) return null;
  return (
    <div className="mb-6">
      <h4 className={`mb-3 text-xs font-bold uppercase tracking-widest ${color}`}>{title}</h4>
      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <div key={item.document_type} className="flex items-start gap-3 rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3">
            <span className={`mt-0.5 text-sm ${item.required ? "text-cyan-400" : "text-slate-500"}`}>
              {item.required ? "✓" : "○"}
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
  return (
    <div className={`rounded-xl border p-4 ${SEVERITY_STYLES[d.severity] ?? SEVERITY_STYLES.info}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold capitalize">{d.field.replaceAll("_", " ")}</p>
        <span className="rounded-full border px-2 py-0.5 text-xs capitalize">{d.severity}</span>
      </div>
      <p className="mt-2 text-xs opacity-90">{d.message}</p>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs opacity-75">
        <div><span className="font-medium">{d.document_a}:</span> {d.value_a}</div>
        <div><span className="font-medium">{d.document_b}:</span> {d.value_b}</div>
      </div>
      <p className="mt-2 text-xs italic opacity-75">Fix: {d.suggested_fix}</p>
    </div>
  );
}

function IncentiveCard({ e }: { e: IncentiveEstimate }) {
  return (
    <div className={`rounded-xl border p-4 ${e.eligible ? "border-green-500/30 bg-green-500/10" : "border-white/10 bg-slate-950/60"}`}>
      <div className="flex items-center justify-between">
        <p className="font-semibold text-slate-100">{e.scheme}</p>
        <span className={`text-xs font-bold ${e.eligible ? "text-green-400" : "text-slate-500"}`}>
          {e.eligible ? "Eligible" : "Not eligible"}
        </span>
      </div>
      {e.eligible && e.estimated_amount != null && (
        <p className="mt-1 text-lg font-bold text-green-400">
          ₹{e.estimated_amount.toLocaleString("en-IN")}
          {e.rate_percent != null && <span className="ml-2 text-sm font-normal text-green-600">@ {e.rate_percent}%</span>}
        </p>
      )}
      <p className="mt-1 text-xs text-slate-400">{e.notes}</p>
      {e.action_items.length > 0 && (
        <ul className="mt-2 list-inside list-disc text-xs text-slate-400">
          {e.action_items.map((a, i) => <li key={i}>{a}</li>)}
        </ul>
      )}
    </div>
  );
}

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

  const docsQuery = useQuery({
    queryKey: ["documents", id, token],
    queryFn: () => api.listDocuments(id!, token!),
    enabled: Boolean(id && token && tab === "documents"),
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

  const logoutMutation = useMutation({
    mutationFn: async () => { if (token) await api.logout(token); },
    onSettled: () => setSession(null),
  });

  const s = shipmentQuery.data;
  const TABS: { key: Tab; label: string }[] = [
    { key: "checklist", label: "1. Checklist" },
    { key: "documents", label: "2. Upload docs" },
    { key: "report", label: "3. Verify" },
    { key: "expert", label: "4. Expert review" },
  ];

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <button onClick={() => navigate("/shipments")} className="mb-3 text-sm text-slate-500 hover:text-slate-300">
        ← Back to shipments
      </button>

      {s && (
        <div className="mb-5 rounded-2xl border border-white/10 bg-slate-900/60 px-5 py-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold">{s.product_name}</h2>
              <p className="text-sm text-slate-400">HSN {s.hsn_code} · {s.destination_country} · {s.incoterm} · {s.payment_term}</p>
            </div>
            <span className="rounded-full border border-white/10 px-3 py-1 text-xs capitalize text-slate-400">
              {s.shipment_mode} · {s.shipment_stage.replace("_", " ")}
            </span>
          </div>
          {s.fob_value && (
            <p className="mt-2 text-sm text-slate-500">FOB {s.invoice_currency} {s.fob_value.toLocaleString()}</p>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="mb-5 flex gap-1 rounded-xl border border-white/10 bg-slate-900/40 p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded-lg py-2 text-xs font-medium transition-colors md:text-sm ${
              tab === t.key
                ? "bg-cyan-500/20 text-cyan-300"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab: Checklist */}
      {tab === "checklist" && (
        <Card>
          <CardHeader>
            <CardTitle>Document Checklist</CardTitle>
            <CardDescription>AI-generated based on your shipment profile. Verify with your CHA.</CardDescription>
          </CardHeader>
          <CardContent>
            {checklistQuery.isLoading && <p className="text-sm text-slate-400">Generating checklist…</p>}
            {checklistQuery.isError && (
              <p className="text-sm text-rose-400">{checklistQuery.error instanceof Error ? checklistQuery.error.message : "Error"}</p>
            )}
            {checklistQuery.data && (
              <>
                <ChecklistSection title="Required documents" items={checklistQuery.data.required} color="text-cyan-400" />
                <ChecklistSection title="Country-specific" items={checklistQuery.data.country_specific} color="text-violet-400" />
                <ChecklistSection title="Bank & payment" items={checklistQuery.data.bank_payment} color="text-amber-400" />
                <ChecklistSection title="Incentive & refund" items={checklistQuery.data.incentive_refund} color="text-green-400" />
                <ChecklistSection title="Optional" items={checklistQuery.data.optional} color="text-slate-400" />
                <p className="mt-4 text-xs text-slate-600">{checklistQuery.data.disclaimer}</p>
                <Button className="mt-4" onClick={() => setTab("documents")}>Upload documents →</Button>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab: Documents */}
      {tab === "documents" && (
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Upload Document</CardTitle>
              <CardDescription>PDF, JPEG, PNG, or Excel. Max 10 MB per file.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 md:flex-row md:items-end">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium uppercase tracking-wider text-slate-400">Document type</label>
                <select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value as DocumentType)}
                  className="rounded-xl border border-white/10 bg-slate-950/80 px-4 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400/40"
                >
                  {Object.entries(DOCUMENT_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium uppercase tracking-wider text-slate-400">File</label>
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
                {uploadMutation.isPending ? "Uploading…" : "Upload"}
              </Button>
            </CardContent>
            {uploadMutation.isError && (
              <div className="mx-6 mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300">
                {uploadMutation.error instanceof Error ? uploadMutation.error.message : "Upload failed."}
              </div>
            )}
            {uploadMutation.isSuccess && (
              <div className="mx-6 mb-4 rounded-xl border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-300">
                Document uploaded successfully.
              </div>
            )}
          </Card>

          <Card>
            <CardHeader><CardTitle>Uploaded documents</CardTitle></CardHeader>
            <CardContent>
              {docsQuery.isLoading && <p className="text-sm text-slate-400">Loading…</p>}
              {docsQuery.data?.length === 0 && (
                <p className="text-sm text-slate-500">No documents uploaded yet.</p>
              )}
              <div className="flex flex-col gap-2">
                {docsQuery.data?.map((doc) => (
                  <div key={doc.id} className="rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-slate-100">{DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type}</p>
                        <p className="text-xs text-slate-500">{doc.file_name} · {doc.file_size_bytes ? `${(doc.file_size_bytes / 1024).toFixed(0)} KB` : ""}</p>
                      </div>
                      <span className={`text-xs ${doc.upload_status === "extracted" ? "text-green-400" : doc.upload_status === "failed" ? "text-rose-400" : "text-amber-400"}`}>
                        {doc.upload_status}
                      </span>
                    </div>
                    <ExtractedFieldsPanel doc={doc} />
                  </div>
                ))}
              </div>
              {(docsQuery.data?.length ?? 0) > 0 && (
                <Button className="mt-4" onClick={() => setTab("report")}>Run verification →</Button>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tab: Report */}
      {tab === "report" && (
        <div className="flex flex-col gap-4">
          {reportQuery.isLoading && (
            <Card><CardContent className="py-8 text-center text-sm text-slate-400">Running AI verification…</CardContent></Card>
          )}
          {reportQuery.isError && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
              {reportQuery.error instanceof Error ? reportQuery.error.message : "Verification failed."}
            </div>
          )}
          {reportQuery.data && (() => {
            const r = reportQuery.data;
            return (
              <>
                <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-900/60 px-5 py-4">
                  <div>
                    <p className="text-xs text-slate-400 uppercase tracking-wider">Overall risk</p>
                    <span className={`mt-1 inline-block rounded-full border px-3 py-1 text-sm font-bold capitalize ${RISK_STYLES[r.overall_risk] ?? ""}`}>
                      {r.overall_risk}
                    </span>
                  </div>
                  <div className="ml-auto text-right">
                    <p className="text-xs text-slate-400 uppercase tracking-wider">Finance readiness</p>
                    <p className="mt-1 text-2xl font-bold text-slate-100">{r.finance_readiness_score}<span className="text-sm text-slate-500">/100</span></p>
                  </div>
                </div>

                {r.missing_documents.length > 0 && (
                  <Card>
                    <CardHeader><CardTitle className="text-rose-400">Missing documents</CardTitle></CardHeader>
                    <CardContent>
                      <ul className="list-inside list-disc text-sm text-slate-300 space-y-1">
                        {r.missing_documents.map((d, i) => <li key={i}>{d}</li>)}
                      </ul>
                    </CardContent>
                  </Card>
                )}

                {r.discrepancies.length > 0 && (
                  <Card>
                    <CardHeader><CardTitle>Discrepancies found</CardTitle></CardHeader>
                    <CardContent className="flex flex-col gap-3">
                      {r.discrepancies.map((d, i) => <DiscrepancyCard key={i} d={d} />)}
                    </CardContent>
                  </Card>
                )}

                <Card>
                  <CardHeader><CardTitle>Incentive estimates</CardTitle></CardHeader>
                  <CardContent className="grid gap-3 md:grid-cols-2">
                    {r.incentive_estimates.map((e, i) => <IncentiveCard key={i} e={e} />)}
                  </CardContent>
                </Card>

                {(r.ebrc_gst_reminders.length > 0 || r.recommendations.length > 0) && (
                  <Card>
                    <CardHeader><CardTitle>Action items</CardTitle></CardHeader>
                    <CardContent className="flex flex-col gap-2">
                      {r.recommendations.map((rec, i) => (
                        <div key={i} className="flex gap-2 text-sm text-slate-300">
                          <span className="mt-0.5 text-cyan-400">→</span>{rec}
                        </div>
                      ))}
                      {r.ebrc_gst_reminders.map((rem, i) => (
                        <div key={i} className="flex gap-2 text-sm text-amber-300">
                          <span className="mt-0.5">⚠</span>{rem}
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                )}

                <p className="text-xs text-slate-600">{r.disclaimer}</p>
                <Button onClick={() => setTab("expert")}>Get expert review →</Button>
              </>
            );
          })()}
        </div>
      )}

      {/* Tab: Expert review */}
      {tab === "expert" && (
        <Card>
          <CardHeader>
            <CardTitle>Expert Review</CardTitle>
            <CardDescription>Have a licensed export documentation expert review this shipment audit report.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">
            <div className="grid gap-4 md:grid-cols-3">
              {[
                { tier: "Basic AI check", price: "₹999", desc: "AI report with priority support response within 24 hrs." },
                { tier: "Expert audit", price: "₹4,999", desc: "Licensed CHA reviews your documents and report. Written feedback within 48 hrs.", highlight: true },
                { tier: "Full advisory", price: "₹9,999", desc: "CHA + CA review. Includes RoDTEP claim filing guidance and eBRC tracking." },
              ].map((plan) => (
                <div key={plan.tier} className={`rounded-2xl border p-5 flex flex-col gap-3 ${plan.highlight ? "border-cyan-400/30 bg-cyan-400/5" : "border-white/10 bg-slate-950/60"}`}>
                  <p className="text-xs font-bold uppercase tracking-widest text-slate-400">{plan.tier}</p>
                  <p className={`text-2xl font-bold ${plan.highlight ? "text-cyan-300" : "text-slate-100"}`}>{plan.price}</p>
                  <p className="text-sm text-slate-400">{plan.desc}</p>
                  <Button variant={plan.highlight ? "default" : "secondary"} className="mt-auto">
                    Request review
                  </Button>
                </div>
              ))}
            </div>
            <div className="rounded-xl border border-white/10 bg-slate-950/60 px-5 py-4 text-sm text-slate-400">
              <p className="font-medium text-slate-300 mb-1">What experts check</p>
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
