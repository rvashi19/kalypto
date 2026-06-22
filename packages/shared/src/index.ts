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
  last_scraped_date: string;
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
  status: "needs_more_info" | "answered" | "insufficient_data";
  session_id: string | null;
  answer: string;
  follow_up_questions: string[];
  sections: ComplianceCheckerSections;
  confidence_level: "High" | "Medium" | "Low";
  confidence_explanation: string;
  unresolved_questions: string[];
  disclaimer: string;
}