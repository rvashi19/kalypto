export type MembershipRole = "owner" | "staff" | "read_only";

export interface UserSummary {
  id: string;
  email: string;
  full_name: string | null;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
}

export interface MembershipSummary {
  organization_id: string;
  role: MembershipRole;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: UserSummary;
  organization: OrganizationSummary;
  membership: MembershipSummary;
}

export interface CurrentUserResponse {
  user: UserSummary;
  organization: OrganizationSummary;
  membership: MembershipSummary;
}

export interface DashboardOverview {
  organization_id: string;
  organization_name: string;
  role: MembershipRole;
  message: string;
}

export interface DocumentationAssistantStatus {
  configured: boolean;
  model: string;
  message: string;
}

export interface DocumentationAssistantResponse {
  answer: string;
  configured: boolean;
  model: string;
}

// ── Shipment types ─────────────────────────────────────────────────────────────

export type ShipmentMode = "sea" | "air" | "courier";
export type ShipmentStage = "pre_shipment" | "post_shipment";
export type DocumentType =
  | "proforma_invoice"
  | "commercial_invoice"
  | "packing_list"
  | "purchase_order"
  | "bl_awb"
  | "shipping_bill"
  | "certificate_of_origin"
  | "insurance"
  | "inspection_certificate"
  | "phytosanitary_certificate"
  | "fumigation_certificate"
  | "ebrc"
  | "other";
export type DocumentUploadStatus = "pending" | "extracted" | "failed";

export interface ShipmentCreate {
  exporter_name: string;
  product_name: string;
  hsn_code: string;
  destination_country: string;
  buyer_country: string;
  incoterm: string;
  payment_term: string;
  shipment_mode: ShipmentMode;
  container_type?: string | null;
  shipment_stage: ShipmentStage;
  fob_value?: number | null;
  invoice_currency: string;
  shipping_bill_no?: string | null;
  port_of_loading?: string | null;
  shipment_date?: string | null;
}

export interface ShipmentResponse {
  id: string;
  tenant_id: string;
  exporter_name: string;
  product_name: string;
  hsn_code: string;
  destination_country: string;
  buyer_country: string;
  incoterm: string;
  payment_term: string;
  shipment_mode: ShipmentMode;
  container_type: string | null;
  shipment_stage: ShipmentStage;
  fob_value: number | null;
  invoice_currency: string;
  shipping_bill_no: string | null;
  port_of_loading: string | null;
  shipment_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentResponse {
  id: string;
  shipment_id: string;
  tenant_id: string;
  document_type: DocumentType;
  file_name: string;
  file_size_bytes: number | null;
  mime_type: string | null;
  upload_status: DocumentUploadStatus;
  extracted_fields: Record<string, unknown> | null;
  created_at: string;
}

export interface ChecklistItem {
  document_type: string;
  label: string;
  required: boolean;
  reason: string;
}

export interface DocumentChecklist {
  required: ChecklistItem[];
  optional: ChecklistItem[];
  country_specific: ChecklistItem[];
  bank_payment: ChecklistItem[];
  incentive_refund: ChecklistItem[];
  disclaimer: string;
}

export interface DiscrepancyItem {
  field: string;
  severity: "info" | "warn" | "critical";
  document_a: string;
  document_b: string;
  value_a: string;
  value_b: string;
  message: string;
  suggested_fix: string;
}

export interface IncentiveEstimate {
  scheme: string;
  eligible: boolean;
  estimated_amount: number | null;
  rate_percent: number | null;
  notes: string;
  action_items: string[];
}

export interface VerificationReport {
  shipment_id: string;
  overall_risk: "low" | "medium" | "high" | "critical";
  missing_documents: string[];
  discrepancies: DiscrepancyItem[];
  incentive_estimates: IncentiveEstimate[];
  ebrc_gst_reminders: string[];
  finance_readiness_score: number;
  finance_readiness_notes: string;
  recommendations: string[];
  disclaimer: string;
}

export interface HsnRateLookupResponse {
  found: boolean;
  hsn_code: string;
  hsn_prefix_matched: string | null;
  description: string | null;
  duty_drawback_rate: number | null;
  rodtep_rate: number | null;
  rosctl_rate: number | null;
  notes: string | null;
  estimated_amounts_inr: Record<string, number> | null;
  fob_inr_basis: number | null;
  exchange_rate_note: string | null;
  message: string | null;
}
