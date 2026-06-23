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

export interface SourceChangeReviewRequest {
  status: "needs_review" | "reviewed" | "ignored";
  notes?: string | null;
}
