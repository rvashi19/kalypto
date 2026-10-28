import type { ComplianceCheckerRequest, HsnRateLookupResponse } from "@repo/shared";
import { Alert, Badge, Button, Field, Input, Select, Textarea } from "@repo/ui";

import { api } from "../../lib/api";
import { AiBadge } from "../../lib/ui";
import { ErrorBox, Metric, PanelFrame, ResultColumns } from "./tools-shared";
import { formatMoney, type QuoteForm } from "./tools-utils";

export function HsnFinderPanel({
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
          <Input
            className="font-mono"
            value={hsn}
            onChange={(event) => onHsnChange(event.target.value)}
          />
        </Field>
        <Field label="FOB basis in INR" hint="Used only for incentive estimates.">
          <Input
            type="number"
            className="tabular-nums"
            value={hsnFobValue}
            onChange={(event) => onFobChange(event.target.value)}
          />
        </Field>
        <Button loading={isPending} disabled={hsn.length < 4} onClick={onLookup}>
          {isPending ? "Looking up..." : "Find rates"}
        </Button>
      </div>
      {error instanceof Error ? (
        <ErrorBox title="Could not look up rates" message={error.message} />
      ) : null}
      {result ? (
        <div className="mt-5 grid gap-4 lg:grid-cols-[280px_1fr]">
          <div className="rounded-card border border-line bg-surface p-5">
            <p className="text-xs font-medium text-ink-2">Finder status</p>
            <div className="mt-2">
              <Badge tone={result.found ? "success" : "info"}>
                {result.found ? "Approved source found" : "No approved source"}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-ink-2">{result.message ?? result.notes}</p>
            {!result.found ? (
              <Alert tone="info" className="mt-4">
                Import the latest official DGFT/CBIC schedule, keep it as pending, and approve it
                only after operator review. Client screens never show pending or expired rows.
              </Alert>
            ) : null}
            <p className="mt-4 text-xs text-ink-2">{result.disclaimer}</p>
          </div>
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <Metric
                label="RoDTEP"
                value={result.rodtep_rate != null ? `${result.rodtep_rate}%` : "N/A"}
              />
              <Metric
                label="Drawback AIR"
                value={result.duty_drawback_rate != null ? `${result.duty_drawback_rate}%` : "N/A"}
              />
              <Metric
                label="RoSCTL"
                value={result.rosctl_rate != null ? `${result.rosctl_rate}%` : "N/A"}
              />
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
              <div className="rounded-card border border-line bg-surface p-4">
                <h3 className="text-sm font-semibold text-ink">Source evidence</h3>
                <div className="mt-3 grid gap-3">
                  {result.rate_evidence.map((row) => (
                    <div
                      key={`${row.scheme}-${row.version_stamp}`}
                      className="rounded-panel bg-surface-2 p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-semibold text-ink">
                          {row.scheme} · {row.rate}%
                        </p>
                        <Badge tone="success">{row.review_status}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-ink-2">
                        {row.source} · effective {row.effective_date}
                        {row.expires_at ? ` · expires ${row.expires_at}` : ""}
                      </p>
                      {row.source_url ? (
                        <a
                          className="mt-2 inline-block text-xs font-semibold text-brand hover:underline"
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

export function ComplianceCheckerPanel({
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
          <Input
            value={form.product}
            onChange={(event) => onChange({ ...form, product: event.target.value })}
          />
        </Field>
        <Field label="HSN">
          <Input
            className="font-mono"
            value={form.hsn_code ?? ""}
            onChange={(event) => onChange({ ...form, hsn_code: event.target.value })}
          />
        </Field>
        <Field label="Destination">
          <Select
            value={form.destination_country}
            onChange={(event) => onChange({ ...form, destination_country: event.target.value })}
          >
            {[form.destination_country, ...countries]
              .filter((value, index, list) => value && list.indexOf(value) === index)
              .map((country) => (
                <option key={country}>{country}</option>
              ))}
          </Select>
        </Field>
        <Field label="Category">
          <Select
            value={form.category}
            onChange={(event) => onChange({ ...form, category: event.target.value })}
          >
            {[form.category, ...categories]
              .filter((value, index, list) => value && list.indexOf(value) === index)
              .map((category) => (
                <option key={category}>{category}</option>
              ))}
          </Select>
        </Field>
        <Field label="Extra facts">
          <Textarea
            className="min-h-28"
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
                    })
                ),
              })
            }
          />
        </Field>
        <div className="flex items-end">
          <Button className="w-full" loading={isPending} onClick={onCheck}>
            {isPending ? "Checking..." : "Check requirements"}
          </Button>
        </div>
      </div>
      {error instanceof Error ? (
        <ErrorBox title="Could not run the check" message={error.message} />
      ) : null}
      {result ? (
        <div className="mt-5 space-y-4">
          <div className="rounded-card border border-line bg-surface p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="font-semibold text-ink">{result.confidence_level} confidence</p>
              <Badge>{result.status.replaceAll("_", " ")}</Badge>
            </div>
            <p className="mt-2 text-sm text-ink-2">{result.answer}</p>
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

export function QuotePanel({
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
        <Field label="Product">
          <Input value={form.product_name} onChange={(e) => set("product_name", e.target.value)} />
        </Field>
        <Field label="HSN">
          <Input
            className="font-mono"
            value={form.hsn_code}
            onChange={(e) => set("hsn_code", e.target.value)}
          />
        </Field>
        <Field label="Destination">
          <Input
            value={form.destination_country}
            onChange={(e) => set("destination_country", e.target.value)}
          />
        </Field>
        <Field label="Incoterm">
          <Input value={form.incoterm} onChange={(e) => set("incoterm", e.target.value)} />
        </Field>
        <Field label="Currency">
          <Input
            value={form.quote_currency}
            onChange={(e) => set("quote_currency", e.target.value)}
          />
        </Field>
        <Field label="FOB value">
          <Input
            type="number"
            className="tabular-nums"
            value={form.fob_value}
            onChange={(e) => set("fob_value", e.target.value)}
          />
        </Field>
        <Field label="Freight">
          <Input
            type="number"
            className="tabular-nums"
            value={form.freight_value}
            onChange={(e) => set("freight_value", e.target.value)}
          />
        </Field>
        <Field label="Insurance">
          <Input
            type="number"
            className="tabular-nums"
            value={form.insurance_value}
            onChange={(e) => set("insurance_value", e.target.value)}
          />
        </Field>
        <Field label="Destination charges">
          <Input
            type="number"
            className="tabular-nums"
            value={form.destination_charges_value}
            onChange={(e) => set("destination_charges_value", e.target.value)}
          />
        </Field>
        <Field label="Destination duty %" hint="Use broker-confirmed value only.">
          <Input
            type="number"
            className="tabular-nums"
            value={form.destination_duty_percent}
            onChange={(e) => set("destination_duty_percent", e.target.value)}
          />
        </Field>
        <Field label="FX to INR">
          <Input
            type="number"
            className="tabular-nums"
            value={form.exchange_rate_to_inr}
            onChange={(e) => set("exchange_rate_to_inr", e.target.value)}
          />
        </Field>
        <Field label="Domestic charges INR">
          <Input
            type="number"
            className="tabular-nums"
            value={form.domestic_charges_inr}
            onChange={(e) => set("domestic_charges_inr", e.target.value)}
          />
        </Field>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          loading={isPending}
          disabled={!form.fob_value || !form.hsn_code}
          onClick={onCalculate}
        >
          {isPending ? "Calculating..." : "Calculate quote"}
        </Button>
        <p className="text-xs text-ink-2">
          Incentives appear only when tenant-verified rates and INR basis exist.
        </p>
      </div>
      {error instanceof Error ? (
        <ErrorBox title="Could not calculate the quote" message={error.message} />
      ) : null}
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
          <div className="rounded-card border border-line bg-surface p-4">
            <h3 className="text-sm font-semibold text-ink">Calculation trail</h3>
            <div className="mt-3 space-y-2">
              {result.line_items.map((item) => (
                <div
                  key={`${item.label}-${item.currency}`}
                  className="flex justify-between gap-3 text-sm"
                >
                  <span className="text-ink-2">{item.label}</span>
                  <span className="font-medium tabular-nums text-ink">
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
                        `${item.scheme}: ${formatMoney(item.estimated_amount_inr)} at ${item.rate_percent}% (${item.version_stamp})`
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
          <p className="text-xs text-ink-2 xl:col-span-2">{result.disclaimer}</p>
        </div>
      ) : null}
    </PanelFrame>
  );
}
