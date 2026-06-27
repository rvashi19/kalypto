import { createContext } from "react";

import type { AuthResponse } from "@repo/shared";

const STORAGE_KEY = "export-assurance.session";

export interface AuthContextValue {
  session: AuthResponse | null;
  token: string | null;
  setSession: (session: AuthResponse | null) => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function readStoredSession(): AuthResponse | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as AuthResponse;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function persistSession(session: AuthResponse | null) {
  if (session) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    return;
  }

  window.localStorage.removeItem(STORAGE_KEY);
}
