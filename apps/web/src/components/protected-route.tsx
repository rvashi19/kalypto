import { useEffect, type PropsWithChildren } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, useLocation } from "react-router-dom";

import { api, isUnauthorizedError, userMessageForError } from "../lib/api";
import { useAuth } from "../lib/auth";

export function ProtectedRoute({ children }: PropsWithChildren) {
  const { token, setSession } = useAuth();
  const location = useLocation();

  const sessionQuery = useQuery({
    queryKey: ["session-check", token],
    queryFn: () => api.me(token!),
    enabled: Boolean(token),
    retry: false,
    staleTime: 60_000,
  });

  const sessionExpired = isUnauthorizedError(sessionQuery.error);

  useEffect(() => {
    if (sessionExpired) {
      setSession(null);
    }
  }, [sessionExpired, setSession]);

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (sessionExpired) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname, reason: "session-expired" }}
      />
    );
  }

  if (sessionQuery.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-slate-100">
        <div className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/30">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">
            Secure workspace
          </p>
          <h1 className="mt-3 text-xl font-semibold">Checking your session</h1>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            We are confirming your access before opening tenant-scoped shipment and compliance data.
          </p>
        </div>
      </div>
    );
  }

  if (sessionQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-slate-100">
        <div className="w-full max-w-md rounded-2xl border border-amber-300/20 bg-amber-300/10 p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-200">
            Connection check
          </p>
          <h1 className="mt-3 text-xl font-semibold">We could not verify your session</h1>
          <p className="mt-2 text-sm leading-6 text-amber-100/80">
            {userMessageForError(sessionQuery.error)}
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
