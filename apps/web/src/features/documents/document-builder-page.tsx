import { Alert, Button, PageHeader, Tabs } from "@repo/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import {
  DEFAULTS,
  DOC_TYPES,
  EMPTY_ITEM,
  buildPayload,
  num,
  type FormState,
  type ItemRow,
} from "./document-builder-data";
import { ValidationIssues } from "./document-builder-fields";
import {
  ExtractPanel,
  LogoPanel,
  PacksHistory,
  SectionCard,
  type ExtractResult,
} from "./document-builder-panels";
import { FormSections } from "./document-builder-sections";

export function DocumentBuilderPage() {
  const { session, token, setSession } = useAuth();
  const qc = useQueryClient();

  const logoutMut = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });
  const logout = () => logoutMut.mutate();

  // Smart extraction state (declared first so `set` closure can reference setMissingFields)
  const [missingFields, setMissingFields] = useState<Set<string>>(new Set());
  const [extractBanner, setExtractBanner] = useState<{
    confidence: number;
    notes: string | null;
    usedLlm: boolean;
    fileName?: string;
  } | null>(null);

  const [form, setForm] = useState<FormState>(DEFAULTS);
  const set = (k: keyof FormState) => (v: string) => {
    setForm((f) => ({ ...f, [k]: v }));
    if (v.trim())
      setMissingFields((s) => {
        const n = new Set(s);
        n.delete(k);
        return n;
      });
  };

  const [items, setItems] = useState<ItemRow[]>([{ ...EMPTY_ITEM }]);

  function applyExtracted(result: ExtractResult) {
    const { extracted, confidence, missing_fields, notes, used_llm } = result;
    const s = (v: unknown) => (v != null && String(v).trim() !== "" ? String(v) : "");

    const exp = (extracted.exporter as Record<string, unknown>) ?? {};
    const byr = (extracted.buyer as Record<string, unknown>) ?? {};
    const shp = (extracted.shipment as Record<string, unknown>) ?? {};
    const pkg = (extracted.packing as Record<string, unknown>) ?? {};
    const dcl = (extracted.declarations as Record<string, unknown>) ?? {};
    const rawItems = (extracted.items as Record<string, unknown>[]) ?? [];

    setForm((prev) => ({
      ...prev,
      ...(s(exp.company_name) && { company_name: s(exp.company_name) }),
      ...(s(exp.address) && { address: s(exp.address) }),
      ...(s(exp.city) && { city: s(exp.city) }),
      ...(s(exp.state) && { state: s(exp.state) }),
      ...(s(exp.postal_code) && { postal_code: s(exp.postal_code) }),
      ...(s(exp.country) && { country: s(exp.country) }),
      ...(s(exp.iec) && { iec: s(exp.iec) }),
      ...(s(exp.gstin) && { gstin: s(exp.gstin) }),
      ...(s(exp.email) && { exporter_email: s(exp.email) }),
      ...(s(exp.bank_name) && { bank_name: s(exp.bank_name) }),
      ...(s(exp.bank_account) && { bank_account: s(exp.bank_account) }),
      ...(s(exp.ifsc_swift) && { ifsc_swift: s(exp.ifsc_swift) }),
      ...(s(exp.ad_code) && { ad_code: s(exp.ad_code) }),
      ...(s(byr.buyer_name) && { buyer_name: s(byr.buyer_name) }),
      ...(s(byr.buyer_address) && { buyer_address: s(byr.buyer_address) }),
      ...(s(byr.buyer_country) && { buyer_country: s(byr.buyer_country) }),
      ...(s(byr.consignee_name) && { consignee_name: s(byr.consignee_name) }),
      ...(s(byr.consignee_address) && { consignee_address: s(byr.consignee_address) }),
      ...(s(shp.invoice_number) && { invoice_number: s(shp.invoice_number) }),
      ...(s(shp.invoice_date) && { invoice_date: s(shp.invoice_date).slice(0, 10) }),
      ...(s(shp.buyer_order_number) && { buyer_order_number: s(shp.buyer_order_number) }),
      ...(s(shp.country_of_origin) && { country_of_origin: s(shp.country_of_origin) }),
      ...(s(shp.country_of_final_destination) && {
        country_of_final_destination: s(shp.country_of_final_destination),
      }),
      ...(s(shp.port_of_loading) && { port_of_loading: s(shp.port_of_loading) }),
      ...(s(shp.port_of_discharge) && { port_of_discharge: s(shp.port_of_discharge) }),
      ...(s(shp.incoterm) && { incoterm: s(shp.incoterm) }),
      ...(s(shp.mode_of_transport) && { mode_of_transport: s(shp.mode_of_transport) }),
      ...(s(shp.currency) && { currency: s(shp.currency) }),
      ...(s(shp.payment_terms) && { payment_terms: s(shp.payment_terms) }),
      ...(s(shp.marks_and_numbers) && { marks_and_numbers: s(shp.marks_and_numbers) }),
      ...(s(pkg.total_packages) && { total_packages: s(pkg.total_packages) }),
      ...(s(pkg.package_type) && { package_type_global: s(pkg.package_type) }),
      ...(s(pkg.total_net_weight) && { total_net_weight: s(pkg.total_net_weight) }),
      ...(s(pkg.total_gross_weight) && { total_gross_weight: s(pkg.total_gross_weight) }),
      ...(s(pkg.freight) && { freight: s(pkg.freight) }),
      ...(s(pkg.insurance) && { insurance: s(pkg.insurance) }),
      ...(s(dcl.authorized_signatory_name) && {
        authorized_signatory_name: s(dcl.authorized_signatory_name),
      }),
      ...(s(dcl.authorized_signatory_designation) && {
        authorized_signatory_designation: s(dcl.authorized_signatory_designation),
      }),
      ...(s(dcl.place_of_issue) && { place_of_issue: s(dcl.place_of_issue) }),
      ...(s(dcl.date_of_issue) && { date_of_issue: s(dcl.date_of_issue).slice(0, 10) }),
    }));

    if (rawItems.length > 0) {
      setItems(
        rawItems.map((it) => ({
          product_description: s(it.product_description),
          hsn_code: s(it.hsn_code),
          quantity: s(it.quantity),
          unit: s(it.unit) || "KGS",
          unit_price: s(it.unit_price),
          total_value: s(it.total_value),
          net_weight: s(it.net_weight),
          gross_weight: s(it.gross_weight),
          package_count: s(it.package_count),
          package_type: s(it.package_type),
        }))
      );
    }

    // Map dotted missing-field paths to form keys for orange highlighting
    const MF_TO_FORM: Record<string, keyof FormState> = {
      "exporter.company_name": "company_name",
      "exporter.iec": "iec",
      "exporter.gstin": "gstin",
      "exporter.address": "address",
      "exporter.bank_name": "bank_name",
      "exporter.bank_account": "bank_account",
      "buyer.buyer_name": "buyer_name",
      "buyer.buyer_country": "buyer_country",
      "shipment.invoice_number": "invoice_number",
      "shipment.incoterm": "incoterm",
      "shipment.currency": "currency",
      "shipment.port_of_loading": "port_of_loading",
      "shipment.port_of_discharge": "port_of_discharge",
      "shipment.payment_terms": "payment_terms",
    };
    const highlighted = new Set<string>();
    for (const mf of missing_fields) {
      const formKey = MF_TO_FORM[mf];
      if (formKey) highlighted.add(formKey);
    }
    setMissingFields(highlighted);
    setExtractBanner({ confidence, notes, usedLlm: used_llm });
  }
  const setItem = (idx: number, k: keyof ItemRow, v: string) =>
    setItems((rows) => rows.map((r, i) => (i === idx ? { ...r, [k]: v } : r)));

  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(
    new Set(DOC_TYPES.map((d) => d.id))
  );
  const toggleDoc = (id: string) =>
    setSelectedDocs((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const [tab, setTab] = useState("build");
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
    onError: () => setSuccessMsg(null),
  });

  const autoTotal = (
    idx: number,
    field: "quantity" | "unit_price" | "total_value",
    value: string
  ) => {
    const row = { ...items[idx], [field]: value };
    const qty = num(row.quantity);
    const price = num(row.unit_price);
    if (field !== "total_value" && qty && price) {
      setItems((rows) =>
        rows.map((r, i) =>
          i === idx ? { ...r, [field]: value, total_value: String((qty * price).toFixed(2)) } : r
        )
      );
    } else {
      setItem(idx, field, value);
    }
  };

  const buildPanel = (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <div className="space-y-4">
        <ExtractPanel token={token!} onExtracted={applyExtracted} />

        {extractBanner && (
          <Alert
            tone={extractBanner.confidence >= 70 ? "success" : "warning"}
            title={`Extracted with ${extractBanner.confidence}% confidence${
              extractBanner.usedLlm ? " (AI)" : " (spreadsheet columns)"
            }.`}
          >
            {missingFields.size > 0 && (
              <p>{missingFields.size} field(s) need your input and are highlighted below.</p>
            )}
            {extractBanner.notes && <p>{extractBanner.notes}</p>}
            <Button
              size="sm"
              variant="ghost"
              className="mt-1"
              onClick={() => {
                setExtractBanner(null);
                setMissingFields(new Set());
              }}
            >
              Dismiss
            </Button>
          </Alert>
        )}

        <FormSections
          form={form}
          set={set}
          missingFields={missingFields}
          items={items}
          setItems={setItems}
          setItem={setItem}
          autoTotal={autoTotal}
        />
      </div>

      <div className="space-y-4">
        <LogoPanel token={token!} />

        <SectionCard title="Documents to generate">
          <div className="space-y-2">
            {DOC_TYPES.map((d) => (
              <label key={d.id} className="flex cursor-pointer items-center gap-2.5">
                <input
                  type="checkbox"
                  checked={selectedDocs.has(d.id)}
                  onChange={() => toggleDoc(d.id)}
                  className="h-4 w-4 accent-brand"
                />
                <span className="text-sm text-ink">{d.label}</span>
              </label>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Check before generating">
          <Button
            size="sm"
            variant="secondary"
            className="w-full"
            onClick={() => {
              setValidationResult(null);
              validateMut.mutate();
            }}
            loading={validateMut.isPending}
          >
            {validateMut.isPending ? "Checking…" : "Validate data"}
          </Button>

          {validateMut.error && (
            <Alert tone="danger" title="Could not validate the data" className="mt-3">
              {(validateMut.error as Error).message}
            </Alert>
          )}

          {validationResult && (
            <div className="mt-3 space-y-2" aria-live="polite">
              <Alert
                tone={validationResult.valid ? "success" : "danger"}
                title={
                  validationResult.valid
                    ? "Ready to generate"
                    : `${validationResult.errors.length} error(s) found`
                }
              />
              <ValidationIssues
                issues={[...validationResult.errors, ...validationResult.warnings]}
              />
            </div>
          )}
        </SectionCard>

        <Button
          className="w-full"
          onClick={() => {
            setSuccessMsg(null);
            generateMut.mutate();
          }}
          loading={generateMut.isPending}
          disabled={selectedDocs.size === 0}
        >
          {generateMut.isPending
            ? "Generating…"
            : `Generate & Download (${selectedDocs.size} doc${selectedDocs.size !== 1 ? "s" : ""})`}
        </Button>

        {successMsg && <Alert tone="success" title={successMsg} />}

        {generateMut.error && (
          <Alert tone="danger" title="Could not generate the documents">
            {(generateMut.error as Error).message}
          </Alert>
        )}

        <Alert tone="info" title="Drafts only">
          Verify with your CHA/customs broker, bank, buyer, and applicable government portals
          (ICEGATE, DGFT, CBIC) before filing or shipment.
        </Alert>
      </div>
    </div>
  );

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={logout}
    >
      <PageHeader
        title="Document builder"
        breadcrumbs={[{ label: "Workspace" }, { label: "Document builder" }]}
        meta={
          <span>
            Generate invoices, packing lists and shipping instructions as drafts for your CHA and
            buyer.
          </span>
        }
      />

      <Tabs
        label="Document builder"
        value={tab}
        onValueChange={setTab}
        tabs={[
          { id: "build", label: "Build documents", panel: buildPanel },
          { id: "history", label: "Saved packs", panel: <PacksHistory token={token!} /> },
        ]}
      />
    </DashboardShell>
  );
}
