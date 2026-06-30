import type {
  AuthResponse,
  ComplianceCheckerRequest,
  ComplianceCheckerResponse,
  ComplianceCoverageResponse,
  ComplianceOptionsResponse,
  ComplianceScrapeRunRequest,
  ComplianceScrapeRunResponse,
  ComplianceRequirementInput,
  ComplianceSourceChangeDetailResponse,
  ComplianceSourceChangeResponse,
  CurrentUserResponse,
  DashboardOverview,
  DiscrepancyDashboardResponse,
  DueComplianceSourceResponse,
  DocumentationAssistantResponse,
  DocumentationAssistantStatus,
  DocumentChecklist,
  DocumentResponse,
  DocumentType,
  ExportQuoteRequest,
  ExportQuoteResponse,
  HsnAiClassifyResponse,
  HsnChapterResponse,
  HsnDetailResponse,
  HsnImportJobResponse,
  HsnImportResponse,
  HsnStatsResponse,
  IncentiveAnomalyResponse,
  IncentiveDetailResponse,
  IncentiveImportJobResponse,
  IncentiveImportResponse,
  IncentiveRateItem,
  IncentiveRefreshResponse,
  IncentiveSearchResponse,
  IncentiveSourceCreate,
  IncentiveSourceResponse,
  HsnRateLookupResponse,
  HsnScrapeRequest,
  HsnSearchResponse,
  HsnVerificationCreate,
  HsnVerificationResponse,
  ShipmentCreate,
  ShipmentImportResponse,
  ReconciliationResponse,
  RateImportResponse,
  RateRecordResponse,
  ShipmentResponse,
  SourceChangeReviewRequest,
  VerificationReport,
} from "@repo/shared";

function normalizeBaseUrl(url: string) {
  return url.replace(/\/+$/, "");
}

function deriveRenderApiBaseUrl() {
  if (typeof window === "undefined") {
    return null;
  }

  const { hostname, protocol } = window.location;
  if (!hostname.endsWith(".onrender.com")) {
    return null;
  }

  if (hostname.includes("-web")) {
    return `${protocol}//${hostname.replace(/-web(?=\.onrender\.com$)/, "-api")}/api/v1`;
  }

  return null;
}

function resolveApiBaseUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (configured && !configured.includes("example.com")) {
    return normalizeBaseUrl(configured);
  }

  const derived = deriveRenderApiBaseUrl();
  if (derived) {
    return normalizeBaseUrl(derived);
  }

  return "http://localhost:8000/api/v1";
}

const API_BASE_URL = resolveApiBaseUrl();

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function detailToMessage(detail: unknown): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    return "Some fields need attention. Please review the form and try again.";
  }

  return "Unexpected API error.";
}

export function isUnauthorizedError(error: unknown) {
  return error instanceof ApiError && error.status === 401;
}

export function userMessageForError(error: unknown) {
  if (isUnauthorizedError(error)) {
    return "Your session has expired. Please sign in again.";
  }

  if (error instanceof Error) {
    if (error.message.toLowerCase().includes("failed to fetch")) {
      return "We could not reach the KALYPTO API. Please make sure the backend is running, then try again.";
    }
    return error.message;
  }

  return "Something went wrong. Please try again.";
}

export interface RegisterPayload {
  email: string;
  password: string;
  organization_name: string;
  organization_slug?: string;
  full_name?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
  organization_id?: string;
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers
      }
    });
  } catch {
    throw new Error(
      "Could not reach the KALYPTO API. If this is the live site, wait for the Render deploy to finish or recheck the API URL."
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({ detail: "Unexpected API error." }))) as {
      detail?: unknown;
    };
    throw new ApiError(response.status, detailToMessage(body.detail), body.detail);
  }

  return (await response.json()) as T;
}

export const api = {
  register: (payload: RegisterPayload) =>
    request<AuthResponse>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),

  login: (payload: LoginPayload) =>
    request<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),

  logout: (token: string) =>
    request<{ success: boolean }>("/auth/logout", { method: "POST" }, token),

  me: (token: string) =>
    request<CurrentUserResponse>("/auth/me", {}, token),

  dashboardOverview: (token: string) =>
    request<DashboardOverview>("/dashboard/overview", {}, token),

  discrepancyDashboard: (token: string) =>
    request<DiscrepancyDashboardResponse>("/dashboard/discrepancies", {}, token),

  documentationAssistantStatus: (token: string) =>
    request<DocumentationAssistantStatus>("/assistant/docs/status", {}, token),

  askDocumentationAssistant: (question: string, token: string) =>
    request<DocumentationAssistantResponse>(
      "/assistant/docs/answer",
      { method: "POST", body: JSON.stringify({ question }) },
      token
    ),

  complianceOptions: (token: string) =>
    request<ComplianceOptionsResponse>("/compliance/options", {}, token),

  askComplianceChecker: (payload: ComplianceCheckerRequest, token: string) =>
    request<ComplianceCheckerResponse>(
      "/compliance/checker/answer",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  dueComplianceSources: (token: string) =>
    request<DueComplianceSourceResponse[]>("/compliance/scrape/due", {}, token),

  runComplianceScrape: (payload: ComplianceScrapeRunRequest, token: string) =>
    request<ComplianceScrapeRunResponse>(
      "/compliance/scrape/run",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  sourceChanges: (token: string, statusFilter = "needs_review") =>
    request<ComplianceSourceChangeResponse[]>(
      `/compliance/scrape/changes?status_filter=${encodeURIComponent(statusFilter)}`,
      {},
      token
    ),

  sourceChangeDetail: (changeId: string, token: string) =>
    request<ComplianceSourceChangeDetailResponse>(
      `/compliance/scrape/changes/${changeId}`,
      {},
      token
    ),

  complianceCoverage: (token: string) =>
    request<ComplianceCoverageResponse>("/compliance/coverage", {}, token),

  ingestComplianceRecords: (records: ComplianceRequirementInput[], token: string) =>
    request<{ created: number; updated: number; total: number }>(
      "/compliance/scrape/ingest",
      { method: "POST", body: JSON.stringify({ records }) },
      token
    ),

  reviewSourceChange: (changeId: string, payload: SourceChangeReviewRequest, token: string) =>
    request<ComplianceSourceChangeResponse>(
      `/compliance/scrape/changes/${changeId}/review`,
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  listRates: (token: string) => request<RateRecordResponse[]>("/rates", {}, token),

  importRates: async (file: File, token: string): Promise<RateImportResponse> => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API_BASE_URL}/rates/import`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form
    });
    const body = await response.json().catch(() => ({ detail: "Rate import failed." }));
    if (!response.ok) {
      throw new Error((body as { detail?: string }).detail ?? "Rate import failed.");
    }
    return body as RateImportResponse;
  },

  // Shipments

  createShipment: (payload: ShipmentCreate, token: string) =>
    request<ShipmentResponse>("/shipments", { method: "POST", body: JSON.stringify(payload) }, token),

  listShipments: (token: string) =>
    request<ShipmentResponse[]>("/shipments", {}, token),

  importShipments: async (file: File, token: string): Promise<ShipmentImportResponse> => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API_BASE_URL}/shipments/import`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form
    });
    const body = await response.json().catch(() => ({ detail: "Import failed." }));
    if (!response.ok) {
      throw new Error((body as { detail?: string }).detail ?? "Import failed.");
    }
    return body as ShipmentImportResponse;
  },

  getShipment: (id: string, token: string) =>
    request<ShipmentResponse>(`/shipments/${id}`, {}, token),

  deleteShipment: async (id: string, token: string): Promise<void> => {
    await fetch(`${API_BASE_URL}/shipments/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
  },

  getChecklist: (shipmentId: string, token: string) =>
    request<DocumentChecklist>(`/shipments/${shipmentId}/checklist`, {}, token),

  listDocuments: (shipmentId: string, token: string) =>
    request<DocumentResponse[]>(`/shipments/${shipmentId}/documents`, {}, token),

  uploadDocument: async (shipmentId: string, documentType: DocumentType, file: File, token: string): Promise<DocumentResponse> => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(
      `${API_BASE_URL}/shipments/${shipmentId}/documents?document_type=${documentType}`,
      { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form }
    );
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: "Upload failed." })) as { detail?: string };
      throw new Error(body.detail ?? "Upload failed.");
    }
    return response.json() as Promise<DocumentResponse>;
  },

  generateDocument: (shipmentId: string, documentType: DocumentType, token: string) =>
    request<DocumentResponse>(
      `/shipments/${shipmentId}/documents/generate/${documentType}`,
      { method: "POST" },
      token
    ),

  downloadDocument: async (
    shipmentId: string,
    documentId: string,
    fileName: string,
    token: string
  ): Promise<void> => {
    const response = await fetch(
      `${API_BASE_URL}/shipments/${shipmentId}/documents/${documentId}/download`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) {
      throw new Error("Document download failed.");
    }
    const objectUrl = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = fileName;
    anchor.click();
    URL.revokeObjectURL(objectUrl);
  },

  verifyShipment: (shipmentId: string, token: string) =>
    request<VerificationReport>(`/shipments/${shipmentId}/verify`, {}, token),

  reconcileShipment: (shipmentId: string, token: string) =>
    request<ReconciliationResponse>(
      `/shipments/${shipmentId}/reconcile`,
      { method: "POST" },
      token
    ),

  getHsnRates: (hsn: string, token: string, fobValue?: number) =>
    request<HsnRateLookupResponse>(
      `/shipments/hsn-rates?hsn=${encodeURIComponent(hsn)}${fobValue ? `&fob_value=${fobValue}` : ""}`,
      {},
      token
    ),

  // HSN Finder (standalone classification) — decoupled from incentives.

  hsnStats: (token: string) => request<HsnStatsResponse>("/hsn/stats", {}, token),

  hsnChapters: (token: string) => request<HsnChapterResponse[]>("/hsn/chapters", {}, token),

  searchHsn: (
    query: string,
    token: string,
    options: { limit?: number; digitLevel?: number } = {}
  ) => {
    const params = new URLSearchParams({ q: query });
    if (options.limit) params.set("limit", String(options.limit));
    if (options.digitLevel) params.set("digit_level", String(options.digitLevel));
    return request<HsnSearchResponse>(`/hsn/search?${params.toString()}`, {}, token);
  },

  getHsnDetail: (code: string, token: string) =>
    request<HsnDetailResponse>(`/hsn/${encodeURIComponent(code)}`, {}, token),

  createHsnVerification: (payload: HsnVerificationCreate, token: string) =>
    request<HsnVerificationResponse>(
      "/hsn/verify",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  classifyHsnAi: (product: string, token: string) =>
    request<HsnAiClassifyResponse>(
      "/hsn/classify-ai",
      { method: "POST", body: JSON.stringify({ product, store: true }) },
      token
    ),

  scrapeHsn: (payload: HsnScrapeRequest, token: string) =>
    request<HsnImportResponse>(
      "/hsn/scrape",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  listHsnImportJobs: (token: string) =>
    request<HsnImportJobResponse[]>("/hsn/import/jobs", {}, token),

  // Incentive Finder — rates for an already-selected HSN (no classification).
  incentiveSearch: (
    hsnCode: string,
    token: string,
    opts: { scheme?: string; exportDate?: string; includeUnapproved?: boolean } = {}
  ) => {
    const params = new URLSearchParams({ hsn_code: hsnCode });
    if (opts.scheme && opts.scheme !== "all") params.set("scheme", opts.scheme);
    if (opts.exportDate) params.set("export_date", opts.exportDate);
    if (opts.includeUnapproved) params.set("include_unapproved", "true");
    return request<IncentiveSearchResponse>(`/incentives/search?${params.toString()}`, {}, token);
  },

  getIncentive: (id: string, token: string) =>
    request<IncentiveDetailResponse>(`/incentives/${id}`, {}, token),

  approveIncentive: (id: string, token: string) =>
    request<IncentiveDetailResponse>(`/incentives/${id}/approve`, { method: "POST" }, token),

  rejectIncentive: (id: string, token: string) =>
    request<IncentiveDetailResponse>(`/incentives/${id}/reject`, { method: "POST" }, token),

  listIncentiveImportJobs: (token: string) =>
    request<IncentiveImportJobResponse[]>("/incentives/import-jobs", {}, token),

  listIncentiveSources: (token: string) =>
    request<IncentiveSourceResponse[]>("/incentives/sources", {}, token),

  registerIncentiveSource: (payload: IncentiveSourceCreate, token: string) =>
    request<IncentiveSourceResponse>(
      "/incentives/sources",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  refreshIncentiveSource: (id: string, token: string) =>
    request<IncentiveRefreshResponse>(`/incentives/sources/${id}/refresh`, { method: "POST" }, token),

  incentivePendingQueue: (token: string) =>
    request<IncentiveRateItem[]>("/incentives/pending", {}, token),

  incentiveAnomalyCheck: (token: string) =>
    request<IncentiveAnomalyResponse>("/incentives/anomaly-check", { method: "POST" }, token),

  importIncentivesFile: async (
    file: File,
    fields: { source_name: string; scheme?: string; source_url?: string; source_document_title?: string; source_document_date?: string; source_version?: string; import_type?: string },
    token: string
  ): Promise<IncentiveImportResponse> => {
    const form = new FormData();
    form.append("file", file);
    Object.entries(fields).forEach(([k, v]) => {
      if (v) form.append(k, v);
    });
    const response = await fetch(`${API_BASE_URL}/incentives/import`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    const body = await response.json().catch(() => ({ detail: "Import failed." }));
    if (!response.ok) throw new Error((body as { detail?: string }).detail ?? "Import failed.");
    return body as IncentiveImportResponse;
  },

  importIncentives: async (
    file: File,
    fields: { source_name: string; scheme?: string; source_url?: string; source_document_title?: string; source_document_date?: string; source_version?: string },
    token: string
  ): Promise<IncentiveImportResponse> => {
    const form = new FormData();
    form.append("file", file);
    Object.entries(fields).forEach(([k, v]) => {
      if (v) form.append(k, v);
    });
    const response = await fetch(`${API_BASE_URL}/incentives/import`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    const body = await response.json().catch(() => ({ detail: "Import failed." }));
    if (!response.ok) throw new Error((body as { detail?: string }).detail ?? "Import failed.");
    return body as IncentiveImportResponse;
  },

  calculateExportQuote: (payload: ExportQuoteRequest, token: string) =>
    request<ExportQuoteResponse>(
      "/tools/export-quote",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),
};
