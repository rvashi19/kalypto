import type { ExportQuoteCalcRequest, ExportQuoteCalcResponse } from "@repo/shared";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
} from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useLogout } from "../../lib/use-logout";

const INCOTERMS = ["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"];

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
  const { session, token } = useAuth();
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
      "hsn_code",
      "product_description",
      "packaging_description",
      "unit",
      "buyer_name",
      "seller_country",
      "buyer_country",
      "origin_city_or_place",
      "port_of_loading",
      "port_of_discharge",
      "final_destination",
      "notes",
    ];
    textKeys.forEach((k) => {
      if (form[k]) (payload as Record<string, unknown>)[k] = form[k];
    });
    const numKeys = [
      "product_value",
      "fx_rate_to_inr",
      "freight_cost",
      "general_insurance",
      "ecgc_premium",
      "destination_handling_charges",
      "import_duty_rate",
      "import_duty_amount",
      "destination_tax_rate",
      "destination_tax_amount",
      "other_destination_charges",
      "commission",
      "exporter_cost_of_goods",
      "exporter_overheads",
      "target_profit_per_unit",
      "target_profit_total",
      ...ORIGIN_FIELDS.map(([k]) => k),
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
  const logoutMutation = useLogout();

  const ccy = form.quote_currency || "INR";

  function renderField([k, label, kind]: FieldDef) {
    const shownLabel = k === "unit_price" ? `${label} (${ccy})` : label;
    if (kind === "incoterm") {
      return (
        <Field key={k} label={shownLabel}>
          <Select value={form[k]} onChange={(e) => set(k, e.target.value)}>
            {INCOTERMS.map((i) => (
              <option key={i}>{i}</option>
            ))}
          </Select>
        </Field>
      );
    }
    const isNumber = kind === "number";
    return (
      <Field key={k} label={shownLabel}>
        <Input
          type={isNumber ? "number" : "text"}
          inputMode={isNumber ? "decimal" : undefined}
          className={isNumber ? "tabular-nums" : undefined}
          value={form[k] ?? ""}
          placeholder={k === "hsn_code" ? "From HSN finder" : undefined}
          onChange={(e) => set(k, e.target.value)}
        />
      </Field>
    );
  }

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <PageHeader
        title="Export quote"
        breadcrumbs={[{ label: "Lookup" }, { label: "Export quote" }]}
        meta={
          <span>
            FOB, CFR, CIF, buyer landed cost and net realization. HSN codes come from the{" "}
            <Link to="/hsn" className="text-brand hover:underline">
              HSN finder
            </Link>
            , approved rates from the{" "}
            <Link to="/incentives" className="text-brand hover:underline">
              incentive finder
            </Link>
            .
          </span>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            calcMutation.mutate();
          }}
        >
          {SECTIONS.map((s) => (
            <Card key={s.title}>
              <CardHeader>
                <SectionTitle>{s.title}</SectionTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
                  {s.fields.map(renderField)}
                </div>
                {s.fields[0][0] === "hsn_code" && !form.hsn_code && (
                  <Hint>Classify the HSN code first for accurate incentives.</Hint>
                )}
                {s.hint && <Hint>{s.hint}</Hint>}
              </CardContent>
            </Card>
          ))}

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" loading={calcMutation.isPending}>
              Calculate
            </Button>
            <Button
              type="button"
              variant="secondary"
              loading={saveMutation.isPending}
              disabled={!result}
              onClick={() => saveMutation.mutate()}
            >
              Save quote
            </Button>
            {saveMutation.data && (
              <Badge tone="success">Saved {saveMutation.data.quote_number}</Badge>
            )}
          </div>
          {calcMutation.error instanceof Error && (
            <Alert tone="danger" title="Could not calculate the quote">
              {calcMutation.error.message}
            </Alert>
          )}
          {saveMutation.error instanceof Error && (
            <Alert tone="danger" title="Could not save the quote">
              {saveMutation.error.message}
            </Alert>
          )}
        </form>

        <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start" aria-live="polite">
          {result ? (
            <Results result={result} ccy={ccy} />
          ) : (
            <EmptyState
              title="No quote yet"
              description="Fill in the form and press Calculate to see FOB, CIF, landed cost and net realization."
            />
          )}
          <SavedQuotes token={token!} onOpen={setResult} />
        </aside>
      </div>
    </DashboardShell>
  );
}

type FieldDef = [key: string, label: string, kind?: "number" | "incoterm"];

const SECTIONS: { title: string; hint?: string; fields: FieldDef[] }[] = [
  {
    title: "Product and HSN",
    fields: [
      ["hsn_code", "HSN code"],
      ["product_description", "Product"],
      ["packaging_description", "Packaging"],
      ["quantity", "Quantity", "number"],
      ["unit", "Unit"],
      ["unit_price", "Unit price", "number"],
    ],
  },
  {
    title: "Route and Incoterm",
    fields: [
      ["seller_country", "Seller country"],
      ["buyer_country", "Buyer country"],
      ["origin_city_or_place", "Origin place"],
      ["port_of_loading", "Port of loading"],
      ["port_of_discharge", "Port of discharge"],
      ["final_destination", "Final destination"],
      ["incoterm", "Incoterm", "incoterm"],
      ["incoterms_version", "Incoterms version"],
      ["quote_currency", "Quote currency"],
      ["fx_rate_to_inr", "FX rate to INR", "number"],
    ],
  },
  {
    title: "Origin and FOB charges (INR)",
    fields: ORIGIN_FIELDS.map(([k, label]): FieldDef => [k, label, "number"]),
  },
  {
    title: "Freight and insurance (INR)",
    fields: [
      ["freight_cost", "Freight", "number"],
      ["general_insurance", "General insurance", "number"],
      ["ecgc_premium", "ECGC premium", "number"],
    ],
  },
  {
    title: "Destination and landed cost (INR)",
    hint: "Import duty and tax rates are user-provided; verify them with destination customs.",
    fields: [
      ["import_duty_rate", "Import duty rate %", "number"],
      ["import_duty_amount", "Import duty amount", "number"],
      ["destination_tax_rate", "Destination tax rate %", "number"],
      ["destination_tax_amount", "Destination tax amount", "number"],
      ["destination_handling_charges", "Destination handling", "number"],
      ["other_destination_charges", "Other destination", "number"],
    ],
  },
  {
    title: "Exporter cost and profit (INR)",
    fields: [
      ["exporter_cost_of_goods", "Cost of goods", "number"],
      ["exporter_overheads", "Overheads", "number"],
      ["commission", "Commission", "number"],
      ["target_profit_per_unit", "Target profit / unit", "number"],
      ["target_profit_total", "Target profit total", "number"],
    ],
  },
];

const inr = (n: number) => "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2 });

function perUnit(inrValue: number, quoteValue: number | null | undefined, ccy: string) {
  return quoteValue != null && ccy !== "INR"
    ? `${inr(inrValue)} · ${quoteValue} ${ccy}`
    : inr(inrValue);
}

function Results({ result, ccy }: { result: ExportQuoteCalcResponse; ccy: string }) {
  return (
    <Card>
      <CardHeader>
        <SectionTitle>Quote result</SectionTitle>
        <p className="text-sm text-ink-2">{result.named_place_summary}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid grid-cols-2 gap-2">
          <Metric label="Product value" value={inr(result.product_value)} />
          <Metric label="Total expenses" value={inr(result.total_origin_charges)} />
          <Metric label="FOB value" value={inr(result.fob_value)} big />
          <Metric
            label="FOB / unit"
            value={perUnit(result.fob_per_unit, result.fob_per_unit_quote_ccy, ccy)}
          />
          <Metric label="CFR value" value={inr(result.cfr_value)} />
          <Metric label="CIF value" value={inr(result.cif_value)} big />
          <Metric
            label="CIF / unit"
            value={perUnit(result.cif_per_unit, result.cif_per_unit_quote_ccy, ccy)}
          />
          <Metric label="Buyer landed cost" value={inr(result.total_landed_cost)} />
          <Metric label="Landed / unit" value={inr(result.landed_cost_per_unit)} />
          <Metric label="Incentive amount" value={inr(result.incentive_amount)} />
          <Metric label="Net realization" value={inr(result.net_exporter_realization)} big />
          <Metric
            label="Margin"
            value={`${inr(result.exporter_margin_amount)} · ${result.exporter_margin_percent}%`}
          />
        </dl>

        {result.incentive_breakdown.length > 0 && (
          <table className="w-full text-sm">
            <caption className="mb-1 text-left text-xs font-medium text-ink-2">
              Incentives (on FOB)
            </caption>
            <tbody>
              {result.incentive_breakdown.map((i) => (
                <tr key={`${i.scheme}-${i.rate_percent}`} className="border-t border-line">
                  <td className="py-1.5">
                    {i.scheme.toUpperCase()} {i.rate_percent}%{" "}
                    {i.source === "approved_source_backed" ? (
                      <Badge tone="success">Approved</Badge>
                    ) : (
                      <Badge tone="warning">User</Badge>
                    )}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{inr(i.amount_inr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {result.warnings.length > 0 && (
          <Alert tone="warning" title="Check before sending">
            <ul className="list-disc space-y-1 pl-4">
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </Alert>
        )}
        <p className="text-xs text-ink-3">{result.disclaimer}</p>
      </CardContent>
    </Card>
  );
}

function SavedQuotes({
  token,
  onOpen,
}: {
  token: string;
  onOpen: (r: ExportQuoteCalcResponse) => void;
}) {
  const quotesQuery = useQuery({
    queryKey: ["export-quotes", token],
    queryFn: () => api.listExportQuotes(token),
  });
  const openMut = useMutation({
    mutationFn: (id: string) => api.getExportQuote(id, token),
    onSuccess: (d) => onOpen(d.calculation),
  });
  const dupMut = useMutation({ mutationFn: (id: string) => api.duplicateExportQuote(id, token) });
  const quotes = quotesQuery.data ?? [];
  if (!quotes.length) return null;
  return (
    <Card>
      <CardHeader>
        <SectionTitle>Saved quotes</SectionTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-line text-sm">
          {quotes.slice(0, 8).map((q) => (
            <li key={q.id} className="flex items-center justify-between gap-2 py-2">
              <button
                type="button"
                className="min-w-0 rounded-sm text-left text-ink hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                onClick={() => openMut.mutate(q.id)}
              >
                <span className="font-mono">{q.quote_number}</span> · {q.incoterm} ·{" "}
                <span className="font-mono">{q.hsn_code ?? "—"}</span> ·{" "}
                <span className="tabular-nums">
                  ₹{q.net_exporter_realization.toLocaleString("en-IN")}
                </span>
              </button>
              <Button size="sm" variant="ghost" onClick={() => dupMut.mutate(q.id)}>
                Duplicate
              </Button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-base font-semibold text-ink">{children}</h2>;
}

function Metric({ label, value, big }: { label: string; value: string; big?: boolean }) {
  return (
    <div className={`rounded-panel bg-surface-2 p-2.5 ${big ? "col-span-2" : ""}`}>
      <dt className="text-xs text-ink-2">{label}</dt>
      <dd className={`mt-0.5 font-semibold tabular-nums text-ink ${big ? "text-lg" : "text-sm"}`}>
        {value}
      </dd>
    </div>
  );
}

function Hint({ children }: { children: ReactNode }) {
  return <p className="mt-3 text-xs text-ink-3">{children}</p>;
}
