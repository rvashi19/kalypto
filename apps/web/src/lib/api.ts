import type {
  AuthResponse,
  CurrentUserResponse,
  DashboardOverview
} from "@repo/shared";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });

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
  dashboardOverview: (token: string) => request<DashboardOverview>("/dashboard/overview", {}, token)
};
