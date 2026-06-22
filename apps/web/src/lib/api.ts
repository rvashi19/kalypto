import type {
  AuthResponse,
  CurrentUserResponse,
  DashboardOverview,
  DocumentationAssistantResponse,
  DocumentationAssistantStatus,
  DocumentChecklist,
  DocumentResponse,
  DocumentType,
  HsnRateLookupResponse,
  ShipmentCreate,
  ShipmentResponse,
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
      detail?: string;
    };
    throw new Error(body.detail ?? "Unexpected API error.");
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

  documentationAssistantStatus: (token: string) =>
    request<DocumentationAssistantStatus>("/assistant/docs/status", {}, token),

  askDocumentationAssistant: (question: string, token: string) =>
    request<DocumentationAssistantResponse>(
      "/assistant/docs/answer",
      { method: "POST", body: JSON.stringify({ question }) },
      token
    ),

  // ── Shipments ────────────────────────────────────────────────────────────────

  createShipment: (payload: ShipmentCreate, token: string) =>
    request<ShipmentResponse>("/shipments", { method: "POST", body: JSON.stringify(payload) }, token),

  listShipments: (token: string) =>
    request<ShipmentResponse[]>("/shipments", {}, token),

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

  verifyShipment: (shipmentId: string, token: string) =>
    request<VerificationReport>(`/shipments/${shipmentId}/verify`, {}, token),

  getHsnRates: (hsn: string, fobValue?: number) =>
    request<HsnRateLookupResponse>(
      `/shipments/hsn-rates?hsn=${encodeURIComponent(hsn)}${fobValue ? `&fob_value=${fobValue}` : ""}`,
    ),
};
