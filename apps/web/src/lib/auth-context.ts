import { createContext } from "react";

import type { AuthResponse, CurrentUserResponse } from "@repo/shared";

export const COOKIE_SESSION_TOKEN = "__cookie_session__";

export type AuthSession = CurrentUserResponse & Partial<Pick<AuthResponse, "expires_at">>;

export interface AuthContextValue {
  session: AuthSession | null;
  token: string | null;
  loading: boolean;
  setSession: (session: AuthSession | AuthResponse | null) => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function toAuthSession(session: AuthSession | AuthResponse): AuthSession {
  return {
    user: session.user,
    organization: session.organization,
    membership: session.membership,
    expires_at: "expires_at" in session ? session.expires_at : undefined,
  };
}
