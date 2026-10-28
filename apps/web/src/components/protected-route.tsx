import { useEffect, type PropsWithChildren, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, useLocation } from "react-router-dom";
import { Alert, Button, Card, Spinner } from "@repo/ui";

import { api, isUnauthorizedError, userMessageForError } from "../lib/api";
import { useAuth } from "../lib/auth";

function CenteredScreen({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-6">
      <Card className="w-full max-w-md space-y-3 p-6">{children}</Card>
    </div>
  );
}

function CheckingSession() {
  return (
    <CenteredScreen>
      <div className="flex items-center gap-3 text-brand">
        <Spinner label="Checking your session" />
        <h1 className="text-base font-semibold text-ink">Checking your session</h1>
      </div>
      <p className="text-sm text-ink-2">
        We are confirming your access before opening tenant-scoped shipment and compliance data.
      </p>
    </CenteredScreen>
  );
}

export function ProtectedRoute({ children }: PropsWithChildren) {
  const { loading, token, setSession } = useAuth();
  const location = useLocation();

  const sessionQuery = useQuery({
    queryKey: ["session-check", token],
    queryFn: () => api.me(token ?? undefined),
    enabled: Boolean(token) && !loading,
    retry: false,
    staleTime: 60_000,
  });

  const sessionExpired = isUnauthorizedError(sessionQuery.error);

  useEffect(() => {
    if (sessionExpired) {
      setSession(null);
    }
  }, [sessionExpired, setSession]);

  if (loading) {
    return <CheckingSession />;
  }

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
    return <CheckingSession />;
  }

  if (sessionQuery.isError) {
    const signOut = () => {
      // Best effort: clear the server cookie, then drop the local session regardless.
      void api
        .logout(token)
        .catch(() => undefined)
        .finally(() => setSession(null));
    };
    return (
      <CenteredScreen>
        <h1 className="text-base font-semibold text-ink">We could not verify your session</h1>
        <Alert tone="warning" title="Connection check">
          {userMessageForError(sessionQuery.error)}
        </Alert>
        <div className="flex gap-2">
          <Button loading={sessionQuery.isFetching} onClick={() => void sessionQuery.refetch()}>
            Retry
          </Button>
          <Button variant="secondary" onClick={signOut}>
            Sign out
          </Button>
        </div>
      </CenteredScreen>
    );
  }

  return <>{children}</>;
}
