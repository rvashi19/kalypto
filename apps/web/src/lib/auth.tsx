import { createContext, useContext, useEffect, useState, type PropsWithChildren } from "react";

import type { AuthResponse } from "@repo/shared";

const STORAGE_KEY = "export-assurance.session";

interface AuthContextValue {
  session: AuthResponse | null;
  token: string | null;
  setSession: (session: AuthResponse | null) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readStoredSession(): AuthResponse | null {
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

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSessionState] = useState<AuthResponse | null>(() => readStoredSession());

  useEffect(() => {
    if (session) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
      return;
    }
    window.localStorage.removeItem(STORAGE_KEY);
  }, [session]);

  const value: AuthContextValue = {
    session,
    token: session?.access_token ?? null,
    setSession: setSessionState
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
