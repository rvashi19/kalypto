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

export interface ComplianceOptionsResponse {
  countries: string[];
  categories: string[];
  recommended_scraping_stack: string[];
  knowledge_store_backend: string;
  refresh_interval_days: number;
}

export interface ComplianceCheckerRequest {
  product: string;
  hsn_code?: string | null;
  destination_country: string;
  category: string;
  details?: Record<string, string | number | boolean | null>;
}

export interface ProductSummary {
  product: string;
  hsn: string | null;
  destination: string;
  category: string;
  assumptions: string[];
}

export interface ComplianceSourceReference {
  source_name: string;
  source_url: string;
  last_checked_date: string | null;
  expires_at: string | null;
  source_authority_level: string;
}

export interface ComplianceCheckerSections {
  product_summary: ProductSummary;
  required_import_documents: string[];
  certificates_required: string[];
  labeling_requirements: string[];
  restriction_alerts: string[];
  inspection_testing_requirements: string[];
  buyer_side_questions: string[];
  source_references: ComplianceSourceReference[];
}

export interface ComplianceCheckerResponse {
  status: "answered" | "insufficient_verified_data" | "needs_review" | "unsupported_scope";
  session_id: string | null;
  answer: string;
  follow_up_questions: string[];
  sections: ComplianceCheckerSections;
  confidence_level: "High" | "Medium" | "Low";
  confidence_explanation: string;
  last_checked_date: string | null;
  unresolved_questions: string[];
  disclaimer: string;
}

// ── Shipment types ─────────────────────────────────────────────────────────────

export interface ComplianceScrapeRunRequest {
  source_url: string;
  country: string;
  category: string;
}

export interface ComplianceScrapeRunResponse {
  run_id: string;
  status: string;
  records_found: number;
  message: string;
}

export interface DiscrepancyDashboardResponse {
  total: number;
  critical: number;
  warning: number;
  lock_risk: number;
  potential_amount: number;
  items: Array<{
    id: string;
    shipment_id: string;
    type: string;
    severity: "info" | "warn" | "critical";
    message: string;
    suggested_fix: string | null;
    lock_risk: boolean;
    potential_amount: number | null;
    created_at: string;
  }>;
  disclaimer: string;
}

export interface DueComplianceSourceResponse {
  source_url: string;
  country: string;
  category: string;
  last_checked_at: string | null;
}

export interface ComplianceSourceChangeResponse {
  id: string;
  source_url: string;
  country: string;
  category: string;
  previous_snapshot_id: string | null;
  current_snapshot_id: string;
  previous_content_hash: string | null;
  current_content_hash: string;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface ComplianceSourceChangeDetailResponse extends ComplianceSourceChangeResponse {
  current_title: string;
  current_scraped_at: string;
  current_markdown_excerpt: string;
  previous_title: string | null;
  previous_scraped_at: string | null;
  previous_markdown_excerpt: string | null;
  excerpt_notice: string;
}

export interface ComplianceCoverageCell {
  country: string;
  category: string;
  total_records: number;
  approved_fresh_records: number;
  pending_or_draft_records: number;
  stale_records: number;
  official_sources: number;
  latest_checked_at: string | null;
  status: "verified" | "partial" | "needs_review" | "empty";
}

export interface ComplianceCoverageResponse {
  refresh_interval_days: number;
  supported_countries: string[];
  supported_categories: string[];
  cells: ComplianceCoverageCell[];
  due_sources_count: number;
  source_changes_needing_review: number;
  disclaimer: string;
}

export interface SourceChangeReviewRequest {
  status: "needs_review" | "reviewed" | "ignored";
  notes?: string | null;
}

export interface ComplianceRequirementInput {
  country: string;
  category: string;
  hsn_code?: string | null;
  product_keywords?: string[];
  requirement_type: string;
  requirement_text: string;
  extracted_requirement?: string | null;
  source_url: string;
  source_name: string;
  source_authority_level?: "official" | "trade_body" | "operator_seeded" | "unknown";
  effective_date?: string | null;
  last_checked_at?: string | null;
  expires_at?: string | null;
  confidence_score?: number;
  status?: "draft" | "active" | "archived";
  review_status?: "pending" | "approved" | "rejected";
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  notes?: string | null;
  unresolved_questions?: string[];
}

export interface ManualComplianceIngestResponse {
  created: number;
  updated: number;
  total: number;
}

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

export interface ShipmentImportResponse {
  created: number;
  failed: number;
  shipments: ShipmentResponse[];
  errors: Array<{ row: number; message: string }>;
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
  document_b: string | null;
  value_a: string;
  value_b: string | null;
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
  rate_evidence: Array<{
    scheme: string;
    rate: number;
    source: string;
    source_url: string | null;
    effective_date: string;
    version_stamp: string;
    confidence: string | null;
    review_status: string;
    reviewed_by: string | null;
    reviewed_at: string | null;
    expires_at: string | null;
    notes: string | null;
  }>;
  disclaimer: string;
}

export interface RateRecordResponse {
  id: string;
  scheme: string;
  hsn: string;
  rate: number;
  source: string;
  source_url: string | null;
  effective_date: string;
  version_stamp: string;
  confidence: string | null;
  review_status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  expires_at: string | null;
  notes: string | null;
}

export interface RateImportResponse {
  created: number;
  failed: number;
  errors: Array<{ row: number; message: string }>;
}

export interface ReconciliationResponse {
  shipment_id: string;
  discrepancies: DiscrepancyDashboardResponse["items"];
  potential_amount: number;
  disclaimer: string;
}

export interface ExportQuoteRequest {
  product_name: string;
  hsn_code: string;
  destination_country: string;
  incoterm: string;
  quote_currency: string;
  fob_value: number;
  freight_value?: number;
  insurance_value?: number;
  destination_charges_value?: number;
  domestic_charges_inr?: number;
  destination_duty_percent?: number | null;
  exchange_rate_to_inr?: number | null;
}

export interface ExportQuoteLineItem {
  label: string;
  amount: number;
  currency: string;
  note: string | null;
}

export interface ExportQuoteIncentiveEstimate {
  scheme: string;
  rate_percent: number;
  estimated_amount_inr: number;
  source: string;
  version_stamp: string;
  confidence: string | null;
}

export interface ExportQuoteResponse {
  product_name: string;
  hsn_code: string;
  destination_country: string;
  incoterm: string;
  quote_currency: string;
  fob_value: number;
  cif_value: number;
  commercial_quote_total: number;
  estimated_destination_duty: number | null;
  buyer_landed_estimate: number;
  exchange_rate_to_inr: number | null;
  fob_value_inr: number | null;
  cif_value_inr: number | null;
  exporter_net_realization_inr: number | null;
  incentive_total_inr: number;
  incentive_estimates: ExportQuoteIncentiveEstimate[];
  line_items: ExportQuoteLineItem[];
  warnings: string[];
  disclaimer: string;
}

// ── HSN Finder (standalone classification module) ──────────────────────────────

export interface HsnHierarchy {
  chapter_code: string | null;
  heading_code: string | null;
  subheading_code: string | null;
  parent_code: string | null;
}

export interface HsnEvidenceItem {
  source_name: string;
  source_url: string | null;
  evidence_type: string;
  document_title: string | null;
  document_date: string | null;
  retrieved_at: string | null;
  raw_text_excerpt: string | null;
  confidence_weight: number | null;
}

export interface HsnSearchItem {
  code: string;
  normalized_code: string;
  description: string;
  digit_level: number;
  hierarchy: HsnHierarchy;
  confidence_score: number;
  confidence_label: "Low" | "Medium" | "High";
  match_reason: string;
  source_evidence: HsnEvidenceItem[];
  warning_flags: string[];
  verification_recommended: boolean;
  verified: boolean;
}

export interface HsnSearchResponse {
  query: string;
  count: number;
  results: HsnSearchItem[];
  disclaimer: string;
}

export interface HsnDetailResponse {
  code: string;
  normalized_code: string;
  description: string;
  digit_level: number;
  hierarchy: HsnHierarchy;
  unit_of_quantity: string | null;
  section_name: string | null;
  chapter_name: string | null;
  import_policy: string | null;
  export_policy: string | null;
  policy_condition: string | null;
  source_name: string;
  source_url: string | null;
  source_document_title: string | null;
  source_document_date: string | null;
  source_version: string | null;
  is_active: boolean;
  source_evidence: HsnEvidenceItem[];
  incentive_rate_available: boolean;
  disclaimer: string;
}

export interface HsnVerificationCreate {
  product_description: string;
  selected_hsn_code?: string | null;
  alternative_hsn_codes?: string[];
  user_notes?: string | null;
}

export interface HsnVerificationResponse {
  id: string;
  product_description: string;
  selected_hsn_code: string | null;
  alternative_hsn_codes: string[];
  user_notes: string | null;
  status: string;
  reviewer_notes: string | null;
  created_at: string;
  disclaimer: string;
}

export interface HsnImportResponse {
  job_id: string;
  status: string;
  import_type: string;
  source_name: string;
  source_version: string | null;
  checksum: string | null;
  records_seen: number;
  records_created: number;
  records_updated: number;
  records_deactivated: number;
  error_message: string | null;
  errors: { row: number; message: string }[];
}

export interface HsnScrapeRequest {
  source: "ogd" | "file" | "eximguru";
  source_version: string;
  source_name?: string | null;
  resource_id?: string | null;
  api_key?: string | null;
  max_records?: number | null;
  url?: string | null;
  import_type?: "csv" | "xlsx" | "json" | null;
  chapters?: number[] | null;
  source_document_title?: string | null;
  source_document_date?: string | null;
}

export interface HsnImportJobResponse {
  id: string;
  source_name: string;
  source_url: string | null;
  import_type: string;
  status: string;
  records_seen: number;
  records_created: number;
  records_updated: number;
  records_deactivated: number;
  error_message: string | null;
  checksum: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_by: string | null;
  created_at: string;
}

export interface HsnCrossCheckSource {
  source: string;
  description: string;
  match: number;
}

export interface HsnAiClassifyResponse {
  product: string;
  hsn_code: string | null;
  in_master: boolean;
  description: string | null;
  confidence: number | null;
  reasoning: string | null;
  alternatives: string[];
  model: string | null;
  stored: boolean;
  verification: "cross_verified" | "exists_weak_match" | "unverified";
  authentic_sources: number;
  cross_check: HsnCrossCheckSource[];
  disclaimer: string;
}

export interface HsnStatsResponse {
  total_codes: number;
  chapters: number;
  headings: number;
  subheadings: number;
  tariff_items: number;
  verified_mappings: number;
}

export interface HsnChapterResponse {
  code: string;
  name: string;
  count: number;
}

// ── Incentive Finder ───────────────────────────────────────────────────────────

export interface IncentiveEvidenceItem {
  source_name: string;
  source_url: string | null;
  document_title: string | null;
  document_date: string | null;
  raw_text_excerpt: string | null;
  retrieved_at: string | null;
  evidence_type: string;
  confidence_weight: number | null;
}

export interface IncentiveRateItem {
  id: string;
  scheme: string;
  hsn_code: string;
  normalized_hsn_code: string;
  digit_level: number;
  product_description: string | null;
  rate_type: string;
  rate_value: number;
  cap_value: number | null;
  cap_unit: string | null;
  unit_of_quantity: string | null;
  condition_text: string | null;
  effective_from: string;
  effective_to: string | null;
  source_name: string;
  source_url: string | null;
  source_document_title: string | null;
  source_document_date: string | null;
  source_version: string | null;
  approval_status: string;
  verified_by: string | null;
  verified_at: string | null;
  is_active: boolean;
  review_note: string | null;
  match_level: string;
  source_evidence_count: number;
}

export interface IncentiveSourceResponse {
  id: string;
  scheme: string | null;
  source_name: string;
  source_url: string | null;
  source_document_title: string | null;
  source_type: string;
  refresh_interval_days: number | null;
  last_fetched_at: string | null;
  last_source_version: string | null;
  last_status: string;
  last_records: number;
  is_active: boolean;
  due_for_refresh: boolean;
  created_at: string;
}

export interface IncentiveSourceCreate {
  source_name: string;
  scheme?: string | null;
  source_url?: string | null;
  source_document_title?: string | null;
  source_type: "csv" | "xlsx" | "pdf" | "json";
  refresh_interval_days?: number | null;
}

export interface IncentiveRefreshResponse {
  source_id: string;
  status: string;
  message: string;
  records_seen: number;
  records_created: number;
  records_updated: number;
}

export interface IncentiveAnomalyResponse {
  checked: number;
  flagged: number;
  model: string | null;
}

export interface IncentiveSearchResponse {
  hsn_code: string;
  normalized_hsn_code: string;
  digit_level: number | null;
  hsn_exists: boolean;
  count: number;
  schemes_present: string[];
  results: IncentiveRateItem[];
  message: string | null;
  disclaimer: string;
}

export interface IncentiveDetailResponse extends IncentiveRateItem {
  source_evidence: IncentiveEvidenceItem[];
  disclaimer: string;
}

export interface IncentiveImportResponse {
  job_id: string;
  status: string;
  scheme: string | null;
  source_name: string;
  import_type: string;
  checksum: string | null;
  records_seen: number;
  records_created: number;
  records_updated: number;
  records_deactivated: number;
  error_message: string | null;
  errors: { row: number; message: string }[];
}

export interface IncentiveImportJobResponse {
  id: string;
  scheme: string | null;
  source_name: string;
  source_url: string | null;
  import_type: string;
  status: string;
  records_seen: number;
  records_created: number;
  records_updated: number;
  records_deactivated: number;
  error_message: string | null;
  checksum: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_by: string | null;
  created_at: string;
}
