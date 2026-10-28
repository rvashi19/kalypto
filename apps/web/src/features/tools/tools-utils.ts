import type { ExportQuoteRequest } from "@repo/shared";

export type QuoteForm = {
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

export const DEFAULT_QUOTE_FORM: QuoteForm = {
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

export function toNumber(value: string): number | undefined {
  if (value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function buildQuotePayload(form: QuoteForm): ExportQuoteRequest {
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

export function formatMoney(value: number | null | undefined, currency = "INR") {
  if (value == null) return "Not available";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}
