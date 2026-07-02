import { Button } from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ChangeEvent } from "react";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

// ── Style constants ──────────────────────────────────────────────────────────

const inputCls =
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-2 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-indigo-400/60 focus:ring-2 focus:ring-indigo-400/20";
const labelCls = "block text-xs font-medium text-slate-400 mb-1";
const sectionCls = "rounded-xl border border-slate-800 bg-slate-900/60 p-5";
const headingCls = "text-sm font-semibold text-slate-200 mb-4";

// ── Types ────────────────────────────────────────────────────────────────────

type Str = string;

interface ItemRow {
  product_description: Str;
  hsn_code: Str;
  quantity: Str;
  unit: Str;
  unit_price: Str;
  total_value: Str;
  net_weight: Str;
  gross_weight: Str;
  package_count: Str;
  package_type: Str;
}

interface FormState {
  // Exporter
  company_name: Str;
  address: Str;
  city: Str;
  state: Str;
  postal_code: Str;
  country: Str;
  iec: Str;
  gstin: Str;
  bank_name: Str;
  bank_account: Str;
  ifsc_swift: Str;
  ad_code: Str;
  exporter_email: Str;
  // Buyer
  buyer_name: Str;
  buyer_address: Str;
  buyer_country: Str;
  consignee_name: Str;
  consignee_address: Str;
  // Shipment
  invoice_number: Str;
  invoice_date: Str;
  buyer_order_number: Str;
  country_of_origin: Str;
  country_of_final_destination: Str;
  port_of_loading: Str;
  port_of_discharge: Str;
  incoterm: Str;
  mode_of_transport: Str;
  currency: Str;
  payment_terms: Str;
  marks_and_numbers: Str;
  // Packing totals
  total_packages: Str;
  package_type_global: Str;
  total_net_weight: Str;
  total_gross_weight: Str;
  freight: Str;
  insurance: Str;
  // Declarations
  authorized_signatory_name: Str;
  authorized_signatory_designation: Str;
  place_of_issue: Str;
  date_of_issue: Str;
}

const DEFAULTS: FormState = {
  company_name: "",
  address: "",
  city: "",
  state: "",
  postal_code: "",
  country: "India",
  iec: "",
  gstin: "",
  bank_name: "",
  bank_account: "",
  ifsc_swift: "",
  ad_code: "",
  exporter_email: "",
  buyer_name: "",
  buyer_address: "",
  buyer_country: "",
  consignee_name: "",
  consignee_address: "",
  invoice_number: "",
  invoice_date: new Date().toISOString().slice(0, 10),
  buyer_order_number: "",
  country_of_origin: "India",
  country_of_final_destination: "",
  port_of_loading: "",
  port_of_discharge: "",
  incoterm: "CIF",
  mode_of_transport: "Sea",
  currency: "USD",
  payment_terms: "",
  marks_and_numbers: "",
  total_packages: "",
  package_type_global: "",
  total_net_weight: "",
  total_gross_weight: "",
  freight: "",
  insurance: "",
  authorized_signatory_name: "",
  authorized_signatory_designation: "",
  place_of_issue: "",
  date_of_issue: new Date().toISOString().slice(0, 10),
};

const EMPTY_ITEM: ItemRow = {
  product_description: "",
  hsn_code: "",
  quantity: "",
  unit: "KGS",
  unit_price: "",
  total_value: "",
  net_weight: "",
  gross_weight: "",
  package_count: "",
  package_type: "",
};

const DOC_TYPES = [
  { id: "proforma_invoice", label: "Proforma Invoice" },
  { id: "commercial_invoice", label: "Commercial Invoice" },
  { id: "packing_list", label: "Packing List" },
  { id: "commercial_invoice_cum_packing_list", label: "Invoice-cum-Packing List" },
  { id: "shipping_instruction", label: "Shipping Instruction (Draft)" },
  { id: "coo_application_data_sheet", label: "CoO Application Data Sheet" },
  { id: "export_document_checklist", label: "Export Document Checklist" },
];

const INCOTERMS = ["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"];
const MODES = ["Sea", "Air", "Road", "Rail", "Multimodal"];
const CURRENCIES = ["USD", "EUR", "GBP", "INR", "AED", "SGD", "CNY", "JPY", "AUD", "CAD"];

// ── Helpers ──────────────────────────────────────────────────────────────────

function num(v: Str) {
  const n = parseFloat(v.replace(",", ""));
  return isNaN(n) ? undefined : n;
}
function int(v: Str) {
  const n = parseInt(v, 10);
  return isNaN(n) ? undefined : n;
}
function str(v: Str) {
  return v.trim() || undefined;
}

function buildPayload(form: FormState, items: ItemRow[]) {
  return {
    exporter: {
      company_name: str(form.company_name) ?? "",
      address: str(form.address) ?? "",
      city: str(form.city),
      state: str(form.state),
      postal_code: str(form.postal_code),
      country: str(form.country) ?? "India",
      iec: str(form.iec),
      gstin: str(form.gstin),
      email: str(form.exporter_email),
      bank_name: str(form.bank_name),
      bank_account: str(form.bank_account),
      ifsc_swift: str(form.ifsc_swift),
      ad_code: str(form.ad_code),
    },
    buyer: {
      buyer_name: str(form.buyer_name) ?? "",
      buyer_address: str(form.buyer_address),
      buyer_country: str(form.buyer_country) ?? "",
      consignee_name: str(form.consignee_name),
      consignee_address: str(form.consignee_address),
    },
    shipment: {
      invoice_number: str(form.invoice_number),
      invoice_date: str(form.invoice_date),
      buyer_order_number: str(form.buyer_order_number),
      country_of_origin: str(form.country_of_origin) ?? "India",
      country_of_final_destination: str(form.country_of_final_destination),
      port_of_loading: str(form.port_of_loading),
      port_of_discharge: str(form.port_of_discharge),
      incoterm: str(form.incoterm),
      incoterms_version: "Incoterms 2020",
      mode_of_transport: str(form.mode_of_transport) ?? "Sea",
      currency: str(form.currency),
      payment_terms: str(form.payment_terms),
      marks_and_numbers: str(form.marks_and_numbers),
    },
    items: items.map((it, i) => ({
      item_number: i + 1,
      product_description: str(it.product_description),
      hsn_code: str(it.hsn_code),
      quantity: num(it.quantity),
      unit: str(it.unit),
      unit_price: num(it.unit_price),
      total_value: num(it.total_value),
      net_weight: num(it.net_weight),
      gross_weight: num(it.gross_weight),
      package_count: int(it.package_count),
      package_type: str(it.package_type),
    })),
    packing: {
      total_packages: int(form.total_packages),
      package_type: str(form.package_type_global),
      total_net_weight: num(form.total_net_weight),
      total_gross_weight: num(form.total_gross_weight),
      freight: num(form.freight),
      insurance: num(form.insurance),
    },
    declarations: {
      authorized_signatory_name: str(form.authorized_signatory_name),
      authorized_signatory_designation: str(form.authorized_signatory_designation),
      place_of_issue: str(form.place_of_issue),
      date_of_issue: str(form.date_of_issue),
    },
  };
}

// ── Sub-components ───────────────────────────────────────────────────────────

function Field({
  label, value, onChange, placeholder, type = "text", required,
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; required?: boolean;
}) {
  return (
    <div>
      <label className={labelCls}>{label}{required && <span className="text-red-400 ml-0.5">*</span>}</label>
      <input
        type={type}
        className={inputCls}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}

function SelectField({
  label, value, onChange, options,
}: {
  label: string; value: string; onChange: (v: string) => void; options: string[];
}) {
  return (
    <div>
      <label className={labelCls}>{label}</label>
      <select
        className={inputCls + " cursor-pointer"}
        value={value}
        onChange={e => onChange(e.target.value)}
      >
        {options.map(o => <option key={o}>{o}</option>)}
      </select>
    </div>
  );
}

function ValidationBadges({ issues }: { issues: { code: string; message: string; severity: string }[] }) {
  if (!issues.length) return null;
  const errors = issues.filter(i => i.severity === "error");
  const warnings = issues.filter(i => i.severity !== "error");
  return (
    <div className="space-y-1.5">
      {errors.map(i => (
        <div key={i.code} className="flex gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          <span className="shrink-0 font-mono text-red-400">{i.code}</span>
          <span>{i.message}</span>
        </div>
      ))}
      {warnings.map(i => (
        <div key={i.code} className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          <span className="shrink-0 font-mono text-amber-400">{i.code}</span>
          <span>{i.message}</span>
        </div>
      ))}
    </div>
  );
}

// ── Logo panel ───────────────────────────────────────────────────────────────

function LogoPanel({ token }: { token: string }) {
  const qc = useQueryClient();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const { data: hasLogo, refetch } = useQuery({
    queryKey: ["org-logo"],
    queryFn: async () => {
      const resp = await fetch(api.getLogoUrl(), {
        headers: { Authorization: `Bearer ${token}` },
      });
      return resp.ok;
    },
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => api.uploadLogo(file, token),
    onSuccess: () => { refetch(); setPreviewUrl(null); },
  });

  const deleteMut = useMutation({
    mutationFn: () => api.deleteLogo(token),
    onSuccess: () => { refetch(); setPreviewUrl(null); },
  });

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    uploadMut.mutate(file);
  }

  return (
    <div className={sectionCls}>
      <p className={headingCls}>Company Logo</p>
      <p className="mb-3 text-xs text-slate-400 leading-relaxed">
        Upload once — your logo will appear on all generated documents automatically. PNG or JPG, under 2 MB.
      </p>

      {(hasLogo || previewUrl) && (
        <div className="mb-3 flex items-center gap-3">
          <img
            src={previewUrl ?? `${api.getLogoUrl()}?t=${Date.now()}`}
            alt="Company logo"
            className="h-12 max-w-[120px] rounded border border-slate-700 bg-white object-contain p-1"
            onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
          />
          <button
            className="text-xs text-slate-500 hover:text-red-400"
            onClick={() => { if (confirm("Remove logo?")) deleteMut.mutate(); }}
            disabled={deleteMut.isPending}
          >
            {deleteMut.isPending ? "Removing…" : "Remove"}
          </button>
        </div>
      )}

      <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-slate-600 bg-slate-800/40 px-3 py-2.5 text-sm text-slate-400 hover:border-indigo-500/60 hover:text-slate-200 transition-colors">
        <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" className="sr-only" onChange={handleFile} />
        {uploadMut.isPending ? "Uploading…" : hasLogo ? "Replace logo" : "Upload logo"}
      </label>

      {uploadMut.error && (
        <p className="mt-1.5 text-xs text-red-400">{(uploadMut.error as Error).message}</p>
      )}
    </div>
  );
}


// ── Packs history panel ──────────────────────────────────────────────────────

function PacksHistory({ token }: { token: string }) {
  const qc = useQueryClient();
  const { data: packs = [] } = useQuery({
    queryKey: ["document-packs"],
    queryFn: () => api.listDocumentPacks(token),
  });

  const downloadMut = useMutation({
    mutationFn: (packId: string) => api.downloadDocumentPack(packId, token),
  });

  const archiveMut = useMutation({
    mutationFn: (packId: string) => api.archiveDocumentPack(packId, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["document-packs"] }),
  });

  if (!packs.length) return (
    <div className="py-8 text-center text-sm text-slate-500">No saved document packs yet.</div>
  );

  return (
    <div className="space-y-2">
      {packs.map(pack => (
        <div key={pack.id} className="flex items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-100">
              {pack.pack_number ?? pack.id.slice(0, 8)}
              {pack.invoice_number && <span className="ml-2 text-slate-400">· {pack.invoice_number}</span>}
            </p>
            <p className="mt-0.5 truncate text-xs text-slate-500">
              {pack.buyer_name ?? "—"} · {pack.destination_country ?? "—"} · {pack.currency} · {pack.status}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button size="sm" variant="secondary" onClick={() => downloadMut.mutate(pack.id)}>
              {downloadMut.isPending ? "…" : "Download"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => { if (confirm("Archive this pack?")) archiveMut.mutate(pack.id); }}
            >
              Archive
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export function DocumentBuilderPage() {
  const { session, token, setSession } = useAuth();
  const qc = useQueryClient();

  const logoutMut = useMutation({
    mutationFn: async () => { if (token) await api.logout(token); },
    onSettled: () => setSession(null),
  });
  const logout = () => logoutMut.mutate();

  const [form, setForm] = useState<FormState>(DEFAULTS);
  const set = (k: keyof FormState) => (v: string) => setForm(f => ({ ...f, [k]: v }));

  const [items, setItems] = useState<ItemRow[]>([{ ...EMPTY_ITEM }]);
  const setItem = (idx: number, k: keyof ItemRow, v: string) =>
    setItems(rows => rows.map((r, i) => i === idx ? { ...r, [k]: v } : r));

  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(
    new Set(DOC_TYPES.map(d => d.id))
  );
  const toggleDoc = (id: string) =>
    setSelectedDocs(s => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const [tab, setTab] = useState<"build" | "history">("build");
  const [validationResult, setValidationResult] = useState<{
    valid: boolean;
    errors: { code: string; message: string; severity: string }[];
    warnings: { code: string; message: string; severity: string }[];
  } | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const validateMut = useMutation({
    mutationFn: () => api.validateDocumentData(buildPayload(form, items), token!),
    onSuccess: (res) => setValidationResult(res),
  });

  const generateMut = useMutation({
    mutationFn: () =>
      api.generateDocuments(buildPayload(form, items), [...selectedDocs], true, token!),
    onSuccess: ({ blob, filename }) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setSuccessMsg(`Downloaded: ${filename}`);
      qc.invalidateQueries({ queryKey: ["document-packs"] });
    },
    onError: (err: Error) => setSuccessMsg(null),
  });

  const autoTotal = (idx: number, field: "quantity" | "unit_price" | "total_value", value: string) => {
    const row = { ...items[idx], [field]: value };
    const qty = num(row.quantity);
    const price = num(row.unit_price);
    if (field !== "total_value" && qty && price) {
      setItems(rows => rows.map((r, i) => i === idx ? { ...r, [field]: value, total_value: String((qty * price).toFixed(2)) } : r));
    } else {
      setItem(idx, field, value);
    }
  };

  const payload = buildPayload(form, items);

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={logout}
    >
      <div className="space-y-6">
        {/* Hero */}
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Document Builder</h1>
          <p className="mt-1 text-sm text-slate-400">
            Generate export documents — invoices, packing lists, shipping instructions, and more — ready for your CHA and buyer.
          </p>
          <p className="mt-1 text-xs text-slate-500">
            All documents are drafts based on your data. Verify with your CHA, bank, buyer, and government portals before filing or shipment.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-xl border border-slate-800 bg-slate-900/40 p-1 w-fit">
          {(["build", "history"] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg px-4 py-1.5 text-sm font-medium transition-colors ${tab === t ? "bg-slate-800 text-white" : "text-slate-400 hover:text-slate-200"}`}
            >
              {t === "build" ? "Build Documents" : "Saved Packs"}
            </button>
          ))}
        </div>

        {tab === "history" ? (
          <PacksHistory token={token!} />
        ) : (
          <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
            {/* Left: form */}
            <div className="space-y-5">

              {/* Exporter */}
              <div className={sectionCls}>
                <p className={headingCls}>Exporter / Shipper</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <Field label="Company Name" value={form.company_name} onChange={set("company_name")} placeholder="Spice Exports Pvt Ltd" required />
                  </div>
                  <div className="sm:col-span-2">
                    <Field label="Address" value={form.address} onChange={set("address")} placeholder="12 Industrial Estate, Unjha" required />
                  </div>
                  <Field label="City" value={form.city} onChange={set("city")} placeholder="Unjha" />
                  <Field label="State" value={form.state} onChange={set("state")} placeholder="Gujarat" />
                  <Field label="Postal Code" value={form.postal_code} onChange={set("postal_code")} placeholder="384170" />
                  <Field label="Country" value={form.country} onChange={set("country")} placeholder="India" />
                  <Field label="IEC" value={form.iec} onChange={set("iec")} placeholder="0900000001" />
                  <Field label="GSTIN" value={form.gstin} onChange={set("gstin")} placeholder="24AAACP0000A1Z5" />
                  <Field label="Bank Name" value={form.bank_name} onChange={set("bank_name")} placeholder="State Bank of India" />
                  <Field label="Account No." value={form.bank_account} onChange={set("bank_account")} placeholder="30000000001" />
                  <Field label="IFSC / SWIFT" value={form.ifsc_swift} onChange={set("ifsc_swift")} placeholder="SBININBB210" />
                  <Field label="AD Code" value={form.ad_code} onChange={set("ad_code")} placeholder="1234567" />
                </div>
              </div>

              {/* Buyer */}
              <div className={sectionCls}>
                <p className={headingCls}>Buyer / Consignee</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <Field label="Buyer Name" value={form.buyer_name} onChange={set("buyer_name")} placeholder="Dubai Spices Trading LLC" required />
                  </div>
                  <div className="sm:col-span-2">
                    <Field label="Buyer Address" value={form.buyer_address} onChange={set("buyer_address")} placeholder="PO Box 12345, Jebel Ali Free Zone, Dubai" />
                  </div>
                  <Field label="Buyer Country" value={form.buyer_country} onChange={set("buyer_country")} placeholder="UAE" required />
                  <Field label="Consignee Name (if different)" value={form.consignee_name} onChange={set("consignee_name")} placeholder="Same as buyer" />
                  <div className="sm:col-span-2">
                    <Field label="Consignee Address" value={form.consignee_address} onChange={set("consignee_address")} placeholder="If different from buyer" />
                  </div>
                </div>
              </div>

              {/* Shipment */}
              <div className={sectionCls}>
                <p className={headingCls}>Shipment Details</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Invoice Number" value={form.invoice_number} onChange={set("invoice_number")} placeholder="SEP/2024-25/001" required />
                  <Field label="Invoice Date" value={form.invoice_date} onChange={set("invoice_date")} type="date" required />
                  <Field label="Buyer PO / Order No." value={form.buyer_order_number} onChange={set("buyer_order_number")} placeholder="PO-2024-001" />
                  <Field label="Country of Origin" value={form.country_of_origin} onChange={set("country_of_origin")} placeholder="India" />
                  <Field label="Country of Final Destination" value={form.country_of_final_destination} onChange={set("country_of_final_destination")} placeholder="UAE" required />
                  <Field label="Port of Loading" value={form.port_of_loading} onChange={set("port_of_loading")} placeholder="Mundra" />
                  <Field label="Port of Discharge" value={form.port_of_discharge} onChange={set("port_of_discharge")} placeholder="Jebel Ali" />
                  <SelectField label="Incoterm" value={form.incoterm} onChange={set("incoterm")} options={INCOTERMS} />
                  <SelectField label="Mode of Transport" value={form.mode_of_transport} onChange={set("mode_of_transport")} options={MODES} />
                  <SelectField label="Currency" value={form.currency} onChange={set("currency")} options={CURRENCIES} />
                  <div className="sm:col-span-2">
                    <Field label="Payment Terms" value={form.payment_terms} onChange={set("payment_terms")} placeholder="30 days from BL date" />
                  </div>
                  <div className="sm:col-span-2">
                    <Field label="Marks & Numbers" value={form.marks_and_numbers} onChange={set("marks_and_numbers")} placeholder="SPICE / JEBEL ALI / 2025 / 001-020" />
                  </div>
                </div>
              </div>

              {/* Line items */}
              <div className={sectionCls}>
                <div className="mb-4 flex items-center justify-between gap-4">
                  <p className={headingCls + " mb-0"}>Line Items</p>
                  <Button size="sm" variant="secondary" onClick={() => setItems(rows => [...rows, { ...EMPTY_ITEM }])}>
                    + Add item
                  </Button>
                </div>
                <div className="space-y-4">
                  {items.map((row, idx) => (
                    <div key={idx} className="rounded-lg border border-slate-700/60 bg-slate-800/40 p-3">
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-400">Item {idx + 1}</span>
                        {items.length > 1 && (
                          <button
                            className="text-xs text-slate-500 hover:text-red-400"
                            onClick={() => setItems(rows => rows.filter((_, i) => i !== idx))}
                          >
                            Remove
                          </button>
                        )}
                      </div>
                      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                        <div className="sm:col-span-2 lg:col-span-2">
                          <Field label="Description" value={row.product_description} onChange={v => setItem(idx, "product_description", v)} placeholder="Cumin Seeds (Cuminum cyminum)" required />
                        </div>
                        <Field label="HSN Code" value={row.hsn_code} onChange={v => setItem(idx, "hsn_code", v)} placeholder="09093129" />
                        <Field label="Quantity" value={row.quantity} onChange={v => autoTotal(idx, "quantity", v)} placeholder="1000" />
                        <Field label="Unit" value={row.unit} onChange={v => setItem(idx, "unit", v)} placeholder="KGS" />
                        <Field label="Unit Price" value={row.unit_price} onChange={v => autoTotal(idx, "unit_price", v)} placeholder="2.00" />
                        <Field label="Total Value" value={row.total_value} onChange={v => autoTotal(idx, "total_value", v)} placeholder="Auto-calculated" />
                        <Field label="Net Weight (kg)" value={row.net_weight} onChange={v => setItem(idx, "net_weight", v)} placeholder="1000" />
                        <Field label="Gross Weight (kg)" value={row.gross_weight} onChange={v => setItem(idx, "gross_weight", v)} placeholder="1050" />
                        <Field label="No. of Packages" value={row.package_count} onChange={v => setItem(idx, "package_count", v)} placeholder="20" />
                        <Field label="Package Type" value={row.package_type} onChange={v => setItem(idx, "package_type", v)} placeholder="Bags" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Packing / freight summary */}
              <div className={sectionCls}>
                <p className={headingCls}>Packing Summary & Freight</p>
                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label="Total Packages" value={form.total_packages} onChange={set("total_packages")} placeholder="20" />
                  <Field label="Package Type" value={form.package_type_global} onChange={set("package_type_global")} placeholder="Bags" />
                  <div />
                  <Field label="Total Net Weight (kg)" value={form.total_net_weight} onChange={set("total_net_weight")} placeholder="1000" />
                  <Field label="Total Gross Weight (kg)" value={form.total_gross_weight} onChange={set("total_gross_weight")} placeholder="1050" />
                  <div />
                  <Field label="Freight" value={form.freight} onChange={set("freight")} placeholder="200.00" />
                  <Field label="Insurance" value={form.insurance} onChange={set("insurance")} placeholder="22.00" />
                </div>
              </div>

              {/* Declarations */}
              <div className={sectionCls}>
                <p className={headingCls}>Declarations & Signatory</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Authorised Signatory Name" value={form.authorized_signatory_name} onChange={set("authorized_signatory_name")} placeholder="Rajesh Patel" />
                  <Field label="Designation" value={form.authorized_signatory_designation} onChange={set("authorized_signatory_designation")} placeholder="Director" />
                  <Field label="Place of Issue" value={form.place_of_issue} onChange={set("place_of_issue")} placeholder="Unjha" />
                  <Field label="Date of Issue" value={form.date_of_issue} onChange={set("date_of_issue")} type="date" />
                </div>
              </div>

            </div>

            {/* Right panel */}
            <div className="space-y-4">

              {/* Logo upload */}
              <LogoPanel token={token!} />

              {/* Document type selector */}
              <div className={sectionCls}>
                <p className={headingCls}>Documents to Generate</p>
                <div className="space-y-2">
                  {DOC_TYPES.map(d => (
                    <label key={d.id} className="flex cursor-pointer items-center gap-2.5">
                      <input
                        type="checkbox"
                        checked={selectedDocs.has(d.id)}
                        onChange={() => toggleDoc(d.id)}
                        className="h-4 w-4 rounded accent-indigo-500"
                      />
                      <span className="text-sm text-slate-300">{d.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Validate */}
              <div className={sectionCls}>
                <p className={headingCls}>Check Before Generating</p>
                <Button
                  size="sm"
                  variant="secondary"
                  className="w-full"
                  onClick={() => { setValidationResult(null); validateMut.mutate(); }}
                  disabled={validateMut.isPending}
                >
                  {validateMut.isPending ? "Checking…" : "Validate Data"}
                </Button>

                {validationResult && (
                  <div className="mt-3 space-y-2">
                    <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${validationResult.valid ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"}`}>
                      {validationResult.valid ? "✓ Ready to generate" : `✗ ${validationResult.errors.length} error(s) found`}
                    </div>
                    <ValidationBadges issues={[...validationResult.errors, ...validationResult.warnings]} />
                  </div>
                )}
              </div>

              {/* Generate */}
              <Button
                className="w-full"
                onClick={() => { setSuccessMsg(null); generateMut.mutate(); }}
                disabled={generateMut.isPending || selectedDocs.size === 0}
              >
                {generateMut.isPending ? "Generating…" : `Generate & Download (${selectedDocs.size} doc${selectedDocs.size !== 1 ? "s" : ""})`}
              </Button>

              {successMsg && (
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
                  {successMsg}
                </div>
              )}

              {generateMut.error && (
                <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                  {(generateMut.error as Error).message}
                </div>
              )}

              {/* Disclaimer */}
              <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-3 py-3 text-xs text-slate-500 leading-relaxed">
                Generated documents are drafts based on your data. Verify with your CHA/customs broker, bank, buyer, and applicable government portals (ICEGATE, DGFT, CBIC) before filing or shipment.
              </div>

            </div>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
