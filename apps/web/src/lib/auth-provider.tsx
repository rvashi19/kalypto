import { useEffect, useState, type PropsWithChildren } from "react";

import { api, isUnauthorizedError } from "./api";
import { AuthContext, COOKIE_SESSION_TOKEN, toAuthSession, type AuthSession } from "./auth-context";
import type { AuthResponse } from "@repo/shared";

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSessionState] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    api
      .me()
      .then((currentSession) => {
        if (mounted) {
          setSessionState(toAuthSession(currentSession));
        }
      })
      .catch((error) => {
        if (mounted && !isUnauthorizedError(error)) {
          console.warn("Session restore failed", error);
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const value = {
    session,
    token: session ? COOKIE_SESSION_TOKEN : null,
    loading,
    setSession: (nextSession: AuthSession | AuthResponse | null) => {
      setSessionState(nextSession ? toAuthSession(nextSession) : null);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
