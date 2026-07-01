import { useEffect, useState, type PropsWithChildren } from "react";

import { AuthContext, persistSession, readStoredSession } from "./auth-context";
import type { AuthResponse } from "@repo/shared";

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSessionState] = useState<AuthResponse | null>(() => readStoredSession());

  useEffect(() => {
    persistSession(session);
  }, [session]);

  const value = {
    session,
    token: session?.access_token ?? null,
    setSession: setSessionState,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
