export type Str = string;

export interface ItemRow {
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

export interface FormState {
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

export const DEFAULTS: FormState = {
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

export const EMPTY_ITEM: ItemRow = {
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

export const DOC_TYPES = [
  { id: "proforma_invoice", label: "Proforma Invoice" },
  { id: "commercial_invoice", label: "Commercial Invoice" },
  { id: "packing_list", label: "Packing List" },
  { id: "commercial_invoice_cum_packing_list", label: "Invoice-cum-Packing List" },
  { id: "shipping_instruction", label: "Shipping Instruction (Draft)" },
  { id: "coo_application_data_sheet", label: "CoO Application Data Sheet" },
  { id: "export_document_checklist", label: "Export Document Checklist" },
];

export const INCOTERMS = [
  "EXW",
  "FCA",
  "FAS",
  "FOB",
  "CFR",
  "CIF",
  "CPT",
  "CIP",
  "DAP",
  "DPU",
  "DDP",
];
export const MODES = ["Sea", "Air", "Road", "Rail", "Multimodal"];
export const CURRENCIES = ["USD", "EUR", "GBP", "INR", "AED", "SGD", "CNY", "JPY", "AUD", "CAD"];

// ── Helpers ──────────────────────────────────────────────────────────────────

export function num(v: Str) {
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

export function buildPayload(form: FormState, items: ItemRow[]) {
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
