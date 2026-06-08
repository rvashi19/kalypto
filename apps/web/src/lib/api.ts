import type {
  AuthResponse,
  CurrentUserResponse,
  DashboardOverview,
  DocumentationAssistantResponse,
  DocumentationAssistantStatus
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
    request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  login: (payload: LoginPayload) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  logout: (token: string) =>
    request<{ success: boolean }>(
      "/auth/logout",
      {
        method: "POST"
      },
      token
    ),
  me: (token: string) => request<CurrentUserResponse>("/auth/me", {}, token),
  dashboardOverview: (token: string) => request<DashboardOverview>("/dashboard/overview", {}, token),
  documentationAssistantStatus: (token: string) =>
    request<DocumentationAssistantStatus>("/assistant/docs/status", {}, token),
  askDocumentationAssistant: (question: string, token: string) =>
    request<DocumentationAssistantResponse>(
      "/assistant/docs/answer",
      {
        method: "POST",
        body: JSON.stringify({ question })
      },
      token
    )
};
