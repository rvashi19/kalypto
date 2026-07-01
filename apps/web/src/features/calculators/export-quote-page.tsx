import type { ExportQuoteCalcRequest, ExportQuoteCalcResponse } from "@repo/shared";
import { Button } from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const INCOTERMS = ["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"];

const inputCls =
  "w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-2 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-amber-400/60 focus:ring-2 focus:ring-amber-400/20";

const ORIGIN_FIELDS: [string, string][] = [
  ["loading_charges", "Loading"],
  ["local_transportation", "Local transport"],
  ["packaging_cost", "Packaging"],
  ["cfs_charges", "CFS"],
  ["terminal_handling_charges", "THC"],
  ["customs_clearance_charges", "Customs clearance"],
  ["local_transit_charges", "Local transit"],
  ["seal_charges", "Seal"],
  ["bill_of_lading_charges", "Bill of lading"],
  ["cha_charges", "CHA"],
  ["phytosanitary_certificate_charges", "Phytosanitary"],
  ["fumigation_charges", "Fumigation"],
  ["vgm_charges", "VGM"],
  ["onsite_inspection_charges", "Inspection"],
  ["bank_transaction_charges", "Bank charges"],
  ["misc_origin_charges", "Misc"],
];

type Form = Record<string, string>;

const DEFAULTS: Form = {
  incoterm: "CIF",
  incoterms_version: "2020",
  quote_currency: "INR",
  hsn_code: "",
  product_description: "Cumin",
  packaging_description: "50 KG PP Bags",
  quantity: "28000",
  unit: "kg",
  unit_price: "125",
  seller_country: "India",
  buyer_country: "United Arab Emirates",
  origin_city_or_place: "Unjha",
  port_of_loading: "Mundra",
  port_of_discharge: "Jebel Ali",
  final_destination: "Dubai",
  fx_rate_to_inr: "83",
  misc_origin_charges: "165900",
  freight_cost: "58100",
};

function num(form: Form, k: string): number | undefined {
  const v = form[k];
  if (v == null || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export function ExportQuotePage() {
  const { session, token, setSession } = useAuth();
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState<Form>({ ...DEFAULTS });
  const [result, setResult] = useState<ExportQuoteCalcResponse | null>(null);

  useEffect(() => {
    const hsn = searchParams.get("hsn_code");
    if (hsn) setForm((f) => ({ ...f, hsn_code: hsn }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function set(k: string, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function buildPayload(extra: Partial<ExportQuoteCalcRequest> = {}): ExportQuoteCalcRequest {
    const payload: ExportQuoteCalcRequest = {
      incoterm: form.incoterm,
      incoterms_version: form.incoterms_version,
      quote_currency: form.quote_currency,
      quantity: num(form, "quantity") ?? 0,
      unit_price: num(form, "unit_price") ?? 0,
      include_incentives: true,
      ...extra,
    };
    const textKeys = [
      "hsn_code", "product_description", "packaging_description", "unit", "buyer_name",
      "seller_country", "buyer_country", "origin_city_or_place", "port_of_loading",
      "port_of_discharge", "final_destination", "notes",
    ];
    textKeys.forEach((k) => {
      if (form[k]) (payload as Record<string, unknown>)[k] = form[k];
    });
    const numKeys = [
      "product_value", "fx_rate_to_inr", "freight_cost", "general_insurance", "ecgc_premium",
      "destination_handling_charges", "import_duty_rate", "import_duty_amount",
      "destination_tax_rate", "destination_tax_amount", "other_destination_charges",
      "commission", "exporter_cost_of_goods", "exporter_overheads", "target_profit_per_unit",
      "target_profit_total", ...ORIGIN_FIELDS.map(([k]) => k),
    ];
    numKeys.forEach((k) => {
      const n = num(form, k);
      if (n !== undefined) (payload as Record<string, unknown>)[k] = n;
    });
    return payload;
  }

  const calcMutation = useMutation({
    mutationFn: () => api.calculateExportQuoteV2(buildPayload(), token!),
    onSuccess: (data) => setResult(data),
  });
  const saveMutation = useMutation({
    mutationFn: () => api.saveExportQuote(buildPayload({ status: "saved" }), token!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["export-quotes"] }),
  });
  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });

  const ccy = form.quote_currency || "INR";

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <section className="rounded-3xl border border-slate-800 bg-gradient-to-b from-slate-900/80 to-slate-950 px-6 py-8 text-center md:py-10">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-amber-300/80">
          — Calculator · FOB · CFR · CIF · Landed Cost —
        </p>
        <h1 className="mt-3 font-serif text-4xl font-bold tracking-tight text-white md:text-5xl">
          Landed Cost / Export Quote
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-400">
          Estimate FOB/CFR/CIF, buyer landed cost, and exporter net realization. HSN classification
          comes from{" "}
          <Link to="/hsn" className="text-amber-300 hover:text-amber-200">HSN Finder</Link> and
          approved incentive rates from{" "}
          <Link to="/incentives" className="text-amber-300 hover:text-amber-200">Incentive Finder</Link>.
        </p>
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_400px]">
        <div className="space-y-5">
          <Panel title="1 · Product & HSN">
            <Grid>
              <Field label="HSN code"><input className={inputCls} value={form.hsn_code} onChange={(e) => set("hsn_code", e.target.value)} placeholder="from HSN Finder" /></Field>
              <Field label="Product"><input className={inputCls} value={form.product_description} onChange={(e) => set("product_description", e.target.value)} /></Field>
              <Field label="Packaging"><input className={inputCls} value={form.packaging_description} onChange={(e) => set("packaging_description", e.target.value)} /></Field>
              <Field label="Quantity"><input className={inputCls} type="number" value={form.quantity} onChange={(e) => set("quantity", e.target.value)} /></Field>
              <Field label="Unit"><input className={inputCls} value={form.unit} onChange={(e) => set("unit", e.target.value)} /></Field>
              <Field label={`Unit price (${ccy})`}><input className={inputCls} type="number" value={form.unit_price} onChange={(e) => set("unit_price", e.target.value)} /></Field>
            </Grid>
            {!form.hsn_code ? <Hint>Select/classify HSN first for better incentive accuracy.</Hint> : null}
          </Panel>

          <Panel title="2 · Route & Incoterm">
            <Grid>
              <Field label="Seller country"><input className={inputCls} value={form.seller_country} onChange={(e) => set("seller_country", e.target.value)} /></Field>
              <Field label="Buyer country"><input className={inputCls} value={form.buyer_country} onChange={(e) => set("buyer_country", e.target.value)} /></Field>
              <Field label="Origin place"><input className={inputCls} value={form.origin_city_or_place} onChange={(e) => set("origin_city_or_place", e.target.value)} /></Field>
              <Field label="Port of loading"><input className={inputCls} value={form.port_of_loading} onChange={(e) => set("port_of_loading", e.target.value)} /></Field>
              <Field label="Port of discharge"><input className={inputCls} value={form.port_of_discharge} onChange={(e) => set("port_of_discharge", e.target.value)} /></Field>
              <Field label="Final destination"><input className={inputCls} value={form.final_destination} onChange={(e) => set("final_destination", e.target.value)} /></Field>
              <Field label="Incoterm">
                <select className={inputCls} value={form.incoterm} onChange={(e) => set("incoterm", e.target.value)}>
                  {INCOTERMS.map((i) => <option key={i}>{i}</option>)}
                </select>
              </Field>
              <Field label="Incoterms version"><input className={inputCls} value={form.incoterms_version} onChange={(e) => set("incoterms_version", e.target.value)} /></Field>
              <Field label="Quote currency"><input className={inputCls} value={form.quote_currency} onChange={(e) => set("quote_currency", e.target.value)} /></Field>
              <Field label="FX rate → INR"><input className={inputCls} type="number" value={form.fx_rate_to_inr} onChange={(e) => set("fx_rate_to_inr", e.target.value)} /></Field>
            </Grid>
          </Panel>

          <Panel title="3 · Origin / FOB charges (INR)">
            <Grid>
              {ORIGIN_FIELDS.map(([k, label]) => (
                <Field key={k} label={label}><input className={inputCls} type="number" value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} /></Field>
              ))}
            </Grid>
          </Panel>

          <Panel title="4 · Freight & Insurance (INR)">
            <Grid>
              <Field label="Freight"><input className={inputCls} type="number" value={form.freight_cost ?? ""} onChange={(e) => set("freight_cost", e.target.value)} /></Field>
              <Field label="General insurance"><input className={inputCls} type="number" value={form.general_insurance ?? ""} onChange={(e) => set("general_insurance", e.target.value)} /></Field>
              <Field label="ECGC premium"><input className={inputCls} type="number" value={form.ecgc_premium ?? ""} onChange={(e) => set("ecgc_premium", e.target.value)} /></Field>
            </Grid>
          </Panel>

          <Panel title="5 · Destination / Landed cost (INR)">
            <Grid>
              <Field label="Import duty rate %"><input className={inputCls} type="number" value={form.import_duty_rate ?? ""} onChange={(e) => set("import_duty_rate", e.target.value)} /></Field>
              <Field label="Import duty amount"><input className={inputCls} type="number" value={form.import_duty_amount ?? ""} onChange={(e) => set("import_duty_amount", e.target.value)} /></Field>
              <Field label="Destination tax rate %"><input className={inputCls} type="number" value={form.destination_tax_rate ?? ""} onChange={(e) => set("destination_tax_rate", e.target.value)} /></Field>
              <Field label="Destination tax amount"><input className={inputCls} type="number" value={form.destination_tax_amount ?? ""} onChange={(e) => set("destination_tax_amount", e.target.value)} /></Field>
              <Field label="Destination handling"><input className={inputCls} type="number" value={form.destination_handling_charges ?? ""} onChange={(e) => set("destination_handling_charges", e.target.value)} /></Field>
              <Field label="Other destination"><input className={inputCls} type="number" value={form.other_destination_charges ?? ""} onChange={(e) => set("other_destination_charges", e.target.value)} /></Field>
            </Grid>
            <Hint>Import duty/tax rates are user-provided and must be verified with destination customs.</Hint>
          </Panel>

          <Panel title="6 · Exporter cost & profit (INR)">
            <Grid>
              <Field label="Cost of goods"><input className={inputCls} type="number" value={form.exporter_cost_of_goods ?? ""} onChange={(e) => set("exporter_cost_of_goods", e.target.value)} /></Field>
              <Field label="Overheads"><input className={inputCls} type="number" value={form.exporter_overheads ?? ""} onChange={(e) => set("exporter_overheads", e.target.value)} /></Field>
              <Field label="Commission"><input className={inputCls} type="number" value={form.commission ?? ""} onChange={(e) => set("commission", e.target.value)} /></Field>
              <Field label="Target profit / unit"><input className={inputCls} type="number" value={form.target_profit_per_unit ?? ""} onChange={(e) => set("target_profit_per_unit", e.target.value)} /></Field>
              <Field label="Target profit total"><input className={inputCls} type="number" value={form.target_profit_total ?? ""} onChange={(e) => set("target_profit_total", e.target.value)} /></Field>
            </Grid>
          </Panel>

          <div className="flex flex-wrap gap-3">
            <Button className="!bg-amber-400 !text-slate-950 hover:!bg-amber-300" disabled={calcMutation.isPending} onClick={() => calcMutation.mutate()}>
              {calcMutation.isPending ? "Calculating…" : "Calculate"}
            </Button>
            <Button variant="secondary" disabled={saveMutation.isPending || !result} onClick={() => saveMutation.mutate()}>
              {saveMutation.isPending ? "Saving…" : "Save quote"}
            </Button>
            {saveMutation.data ? <span className="self-center text-sm text-emerald-300">Saved {saveMutation.data.quote_number}</span> : null}
            {calcMutation.error instanceof Error ? <span className="self-center text-sm text-rose-300">{calcMutation.error.message}</span> : null}
          </div>
        </div>

        <aside className="lg:sticky lg:top-4 lg:self-start space-y-4">
          {result ? <Results result={result} ccy={ccy} /> : (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 text-sm text-slate-500">
              Enter values and press Calculate to see FOB/CIF, landed cost, and net realization.
            </div>
          )}
          <SavedQuotes token={token!} onOpen={setResult} />
        </aside>
      </div>
    </DashboardShell>
  );
}

function Results({ result, ccy }: { result: ExportQuoteCalcResponse; ccy: string }) {
  const inr = (n: number) => "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  return (
    <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-300">{result.named_place_summary}</p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Metric label="Product value" value={inr(result.product_value)} />
        <Metric label="Total expenses" value={inr(result.total_origin_charges)} />
        <Metric label="FOB value" value={inr(result.fob_value)} big />
        <Metric label={`FOB / unit`} value={`${inr(result.fob_per_unit)}${result.fob_per_unit_quote_ccy != null && ccy !== "INR" ? ` · ${result.fob_per_unit_quote_ccy} ${ccy}` : ""}`} />
        <Metric label="CFR value" value={inr(result.cfr_value)} />
        <Metric label="CIF value" value={inr(result.cif_value)} big />
        <Metric label="CIF / unit" value={`${inr(result.cif_per_unit)}${result.cif_per_unit_quote_ccy != null && ccy !== "INR" ? ` · ${result.cif_per_unit_quote_ccy} ${ccy}` : ""}`} />
        <Metric label="Buyer landed cost" value={inr(result.total_landed_cost)} />
        <Metric label="Landed / unit" value={inr(result.landed_cost_per_unit)} />
        <Metric label="Incentive amount" value={inr(result.incentive_amount)} />
        <Metric label="Net realization" value={inr(result.net_exporter_realization)} big />
        <Metric label="Margin" value={`${inr(result.exporter_margin_amount)} · ${result.exporter_margin_percent}%`} />
      </div>

      {result.incentive_breakdown.length ? (
        <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Incentives (on FOB)</p>
          {result.incentive_breakdown.map((i, idx) => (
            <div key={idx} className="mt-1 flex items-center justify-between text-xs text-slate-300">
              <span>{i.scheme.toUpperCase()} {i.rate_percent}% <Badge source={i.source} /></span>
              <span>{inr(i.amount_inr)}</span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="space-y-1">
        {result.warnings.map((w, i) => (
          <p key={i} className="text-[11px] leading-4 text-amber-300/90">⚠ {w}</p>
        ))}
      </div>
      <p className="text-[11px] leading-4 text-slate-500">{result.disclaimer}</p>
    </div>
  );
}

function SavedQuotes({ token, onOpen }: { token: string; onOpen: (r: ExportQuoteCalcResponse) => void }) {
  const quotesQuery = useQuery({ queryKey: ["export-quotes", token], queryFn: () => api.listExportQuotes(token) });
  const openMut = useMutation({ mutationFn: (id: string) => api.getExportQuote(id, token), onSuccess: (d) => onOpen(d.calculation) });
  const dupMut = useMutation({ mutationFn: (id: string) => api.duplicateExportQuote(id, token) });
  const quotes = quotesQuery.data ?? [];
  if (!quotes.length) return null;
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Saved quotes</p>
      <div className="mt-2 space-y-1.5 text-xs">
        {quotes.slice(0, 8).map((q) => (
          <div key={q.id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-800 p-2">
            <button className="text-left text-slate-300 hover:text-amber-200" onClick={() => openMut.mutate(q.id)}>
              {q.quote_number} · {q.incoterm} · {q.hsn_code ?? "—"} · ₹{q.net_exporter_realization.toLocaleString("en-IN")}
            </button>
            <button className="text-slate-500 hover:text-amber-200" onClick={() => dupMut.mutate(q.id)}>Duplicate</button>
          </div>
        ))}
      </div>
    </div>
  );
}

function Badge({ source }: { source: string }) {
  const approved = source === "approved_source_backed";
  return (
    <span className={`ml-1 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase ${approved ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300" : "border-amber-500/40 bg-amber-500/15 text-amber-300"}`}>
      {approved ? "approved" : "user"}
    </span>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-[0.14em] text-amber-300">{title}</h2>
      {children}
    </section>
  );
}

function Grid({ children }: { children: ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{children}</div>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function Metric({ label, value, big }: { label: string; value: string; big?: boolean }) {
  return (
    <div className={`rounded-lg border border-slate-800 bg-slate-950/40 p-2.5 ${big ? "col-span-2" : ""}`}>
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-0.5 font-semibold ${big ? "text-lg text-amber-300" : "text-sm text-slate-100"}`}>{value}</p>
    </div>
  );
}

function Hint({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-[11px] leading-4 text-slate-500">{children}</p>;
}
