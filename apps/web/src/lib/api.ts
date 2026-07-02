import type {
  AuthResponse,
  ComplianceCheckerRequest,
  ComplianceCheckerResponse,
  ComplianceCheckRequestV1,
  ComplianceCheckResponseV1,
  ComplianceCoverageResponse,
  ComplianceOptionsResponse,
  ComplianceScrapeRunRequest,
  ComplianceScrapeRunResponse,
  ComplianceRequirementInput,
  ComplianceSourceChangeDetailResponse,
  ComplianceSourceChangeResponse,
  RetrievalJobResponse,
  ReviewQueueItem,
  SourceRegistryCreateRequest,
  SourceRegistryResponse,
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
  ExportQuoteCalcRequest,
  ExportQuoteCalcResponse,
  ExportQuoteDetailResponse,
  ExportQuoteListItem,
  IncentiveAnomalyResponse,
  IncentiveBulkApproveResponse,
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
import { COOKIE_SESSION_TOKEN } from "./auth-context";

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

function authHeaders(token?: string): HeadersInit {
  if (!token || token === COOKIE_SESSION_TOKEN) {
    return {};
  }

  return { Authorization: `Bearer ${token}` };
}

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
  otp_code?: string;
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(token),
        ...options.headers
      },
      credentials: "include"
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

  logout: (token?: string) =>
    request<{ success: boolean }>("/auth/logout", { method: "POST" }, token),

  me: (token?: string) =>
    request<CurrentUserResponse>("/auth/me", {}, token),

  setupTwoFactor: (token?: string) =>
    request<{ secret: string; otpauth_uri: string }>("/auth/2fa/setup", {}, token),

  enableTwoFactor: (otp_code: string, token?: string) =>
    request<CurrentUserResponse>(
      "/auth/2fa/enable",
      { method: "POST", body: JSON.stringify({ otp_code }) },
      token
    ),

  disableTwoFactor: (otp_code: string, token?: string) =>
    request<CurrentUserResponse>(
      "/auth/2fa/disable",
      { method: "POST", body: JSON.stringify({ otp_code }) },
      token
    ),

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

  // ── Country Compliance Checker v1 ──
  complianceCheck: (payload: ComplianceCheckRequestV1, token: string) =>
    request<ComplianceCheckResponseV1>(
      "/compliance/check",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  complianceCheckSession: (sessionId: string, token: string) =>
    request<ComplianceCheckResponseV1>(`/compliance/sessions/${sessionId}`, {}, token),

  retrievalJob: (jobId: string, token: string) =>
    request<RetrievalJobResponse>(`/compliance/retrieval-jobs/${jobId}`, {}, token),

  complianceReviewQueue: (token: string) =>
    request<ReviewQueueItem[]>("/compliance/review-queue", {}, token),

  approveRequirement: (requirementId: string, token: string, notes?: string) =>
    request<{ requirement_id: string; review_status: string; status: string }>(
      `/compliance/requirements/${requirementId}/approve`,
      { method: "POST", body: JSON.stringify({ notes: notes ?? null }) },
      token
    ),

  rejectRequirement: (requirementId: string, token: string, notes?: string) =>
    request<{ requirement_id: string; review_status: string; status: string }>(
      `/compliance/requirements/${requirementId}/reject`,
      { method: "POST", body: JSON.stringify({ notes: notes ?? null }) },
      token
    ),

  listComplianceSources: (token: string) =>
    request<SourceRegistryResponse[]>("/compliance/sources", {}, token),

  createComplianceSource: (payload: SourceRegistryCreateRequest, token: string) =>
    request<SourceRegistryResponse>(
      "/compliance/sources",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  seedComplianceSources: (token: string) =>
    request<{ created: number; skipped: number; total: number }>(
      "/compliance/sources/seed",
      { method: "POST" },
      token
    ),

  refreshDueComplianceSources: (token: string) =>
    request<{
      due_groups: number;
      jobs_run: number;
      pages_fetched: number;
      snapshots_created: number;
      requirements_extracted: number;
      failures: number;
    }>("/compliance/refresh-due", { method: "POST" }, token),

  listRates: (token: string) => request<RateRecordResponse[]>("/rates", {}, token),

  importRates: async (file: File, token: string): Promise<RateImportResponse> => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API_BASE_URL}/rates/import`, {
      method: "POST",
      headers: authHeaders(token),
      body: form,
      credentials: "include"
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
      headers: authHeaders(token),
      body: form,
      credentials: "include"
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
      headers: authHeaders(token),
      credentials: "include",
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
      { method: "POST", headers: authHeaders(token), body: form, credentials: "include" }
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
      { headers: authHeaders(token), credentials: "include" }
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

  // Landed Cost / Export Quote calculator
  calculateExportQuoteV2: (payload: ExportQuoteCalcRequest, token: string) =>
    request<ExportQuoteCalcResponse>(
      "/calculators/export-quote/calculate",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),
  saveExportQuote: (payload: ExportQuoteCalcRequest, token: string) =>
    request<ExportQuoteDetailResponse>(
      "/calculators/export-quote/save",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),
  listExportQuotes: (token: string) =>
    request<ExportQuoteListItem[]>("/calculators/export-quote", {}, token),
  getExportQuote: (id: string, token: string) =>
    request<ExportQuoteDetailResponse>(`/calculators/export-quote/${id}`, {}, token),
  duplicateExportQuote: (id: string, token: string) =>
    request<ExportQuoteDetailResponse>(`/calculators/export-quote/${id}/duplicate`, { method: "POST" }, token),

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

  bulkApproveIncentives: (token: string, sourceId?: string) =>
    request<IncentiveBulkApproveResponse>(
      "/incentives/bulk-approve",
      { method: "POST", body: JSON.stringify({ source_id: sourceId ?? null }) },
      token
    ),

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
      headers: authHeaders(token),
      body: form,
      credentials: "include",
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
      headers: authHeaders(token),
      body: form,
      credentials: "include",
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

  // Document Builder

  validateDocumentData: (data: unknown, token: string) =>
    request<{ valid: boolean; errors: { code: string; message: string; severity: string }[]; warnings: { code: string; message: string; severity: string }[] }>(
      "/documents/validate",
      { method: "POST", body: JSON.stringify({ data }) },
      token
    ),

  generateDocuments: async (
    data: unknown,
    documentTypes: string[],
    savePack: boolean,
    token: string
  ): Promise<{ blob: Blob; packId: string | null; filename: string }> => {
    const response = await fetch(`${API_BASE_URL}/documents/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ data, document_types: documentTypes, save_pack: savePack }),
      credentials: "include",
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: "Generation failed." })) as { detail?: unknown };
      const msg = typeof body.detail === "string" ? body.detail
        : (body.detail as { message?: string })?.message ?? "Document generation failed.";
      throw new Error(msg);
    }
    const blob = await response.blob();
    const packId = response.headers.get("x-pack-id");
    const disposition = response.headers.get("content-disposition") ?? "";
    const match = disposition.match(/filename="([^"]+)"/);
    return { blob, packId, filename: match?.[1] ?? "ExportDocs.zip" };
  },

  listDocumentPacks: (token: string, limit = 20, offset = 0) =>
    request<Array<{
      id: string; pack_number: string | null; invoice_number: string | null;
      buyer_name: string | null; destination_country: string | null;
      incoterm: string | null; currency: string | null;
      total_invoice_value: number | null; status: string;
      created_at: string; updated_at: string;
    }>>(`/documents/packs?limit=${limit}&offset=${offset}`, {}, token),

  getDocumentPack: (packId: string, token: string) =>
    request<{
      id: string; pack_number: string | null; invoice_number: string | null;
      buyer_name: string | null; destination_country: string | null;
      incoterm: string | null; currency: string | null;
      total_invoice_value: number | null; status: string;
      created_at: string; updated_at: string;
      shipment_data: unknown; generated_documents: unknown[];
    }>(`/documents/packs/${packId}`, {}, token),

  downloadDocumentPack: async (packId: string, token: string): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/documents/packs/${packId}/download`, {
      headers: authHeaders(token),
      credentials: "include",
    });
    if (!response.ok) throw new Error("Download failed.");
    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") ?? "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] ?? `ExportDocs_${packId.slice(0, 8)}.zip`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },

  archiveDocumentPack: async (packId: string, token: string): Promise<void> => {
    await fetch(`${API_BASE_URL}/documents/packs/${packId}`, {
      method: "DELETE",
      headers: authHeaders(token),
      credentials: "include",
    });
  },

  // Organisation logo for document builder

  uploadLogo: async (file: File, token: string): Promise<void> => {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${API_BASE_URL}/documents/logo`, {
      method: "POST",
      headers: authHeaders(token),
      body: form,
      credentials: "include",
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ detail: "Upload failed." })) as { detail?: string };
      throw new Error(body.detail ?? "Logo upload failed.");
    }
  },

  getLogoUrl: () => `${API_BASE_URL}/documents/logo`,

  deleteLogo: async (token: string): Promise<void> => {
    await fetch(`${API_BASE_URL}/documents/logo`, {
      method: "DELETE",
      headers: authHeaders(token),
      credentials: "include",
    });
  },

  uploadImportFile: async (
    file: File,
    token: string,
    sheetName?: string
  ): Promise<{
    session_id: string; original_filename: string; file_type: string;
    sheet_names: string[]; detected_columns: string[];
    suggested_mapping: Record<string, string>;
    parsed_preview: unknown[]; warnings: { code: string; message: string; severity: string }[];
    status: string;
  }> => {
    const form = new FormData();
    form.append("file", file);
    if (sheetName) form.append("sheet_name", sheetName);
    const response = await fetch(`${API_BASE_URL}/documents/import/upload`, {
      method: "POST",
      headers: authHeaders(token),
      body: form,
      credentials: "include",
    });
    const body = await response.json().catch(() => ({ detail: "Upload failed." }));
    if (!response.ok) throw new Error((body as { detail?: string }).detail ?? "Upload failed.");
    return body;
  },

  extractFromDocument: async (
    file: File,
    token: string,
    sheetName?: string
  ): Promise<{
    extracted: Record<string, unknown>;
    confidence: number;
    missing_fields: string[];
    notes: string | null;
    file_type: string;
    used_llm: boolean;
    sheet_names: string[];
  }> => {
    const fd = new FormData();
    fd.append("file", file);
    if (sheetName) fd.append("sheet_name", sheetName);
    const response = await fetch(`${API_BASE_URL}/documents/import/extract`, {
      method: "POST",
      headers: authHeaders(token),
      body: fd,
      credentials: "include",
    });
    const body = await response.json().catch(() => ({ detail: "Extraction failed." }));
    if (!response.ok) throw new Error((body as { detail?: string }).detail ?? "Extraction failed.");
    return body;
  },
};
