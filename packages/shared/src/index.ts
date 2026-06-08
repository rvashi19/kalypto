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
