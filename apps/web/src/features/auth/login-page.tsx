import { useMutation } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@repo/ui";

import { AuthShell } from "../../components/layout/auth-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setSession } = useAuth();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const reason = (location.state as { reason?: string } | null)?.reason;

  useEffect(() => {
    if (reason === "session-expired") {
      navigate("/login", { replace: true, state: { from } });
    }
  }, [from, navigate, reason]);

  const mutation = useMutation({
    mutationFn: async (formData: FormData) =>
      api.login({
        email: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? ""),
      }),
    onSuccess: (session) => {
      setSession(session);
      navigate(from, { replace: true });
    },
  });

  const errorMessage = mutation.isError ? userMessageForError(mutation.error) : null;
  const sessionMessage =
    reason === "session-expired" ? "Your session expired for security. Please sign in again." : null;

  return (
    <AuthShell
      eyebrow="Export assurance platform"
      title="Control export documents, incentives, and compliance from one workspace."
      description="KALYPTO helps Indian exporters prepare shipment records, verify documentation, monitor destination requirements, and keep incentive claims visible."
    >
      <Card>
        <CardHeader>
          <CardTitle>Sign in to KALYPTO</CardTitle>
          <CardDescription>Access your secure export assurance workspace.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              mutation.mutate(new FormData(event.currentTarget));
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="owner@exportco.in"
                defaultValue="demo@example.com"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="Your password"
                defaultValue="DemoPassword123!"
                required
              />
            </div>

            {sessionMessage ? (
              <p
                className="rounded-xl border border-cyan-300/20 bg-cyan-300/10 px-3 py-2 text-sm text-cyan-100"
                role="status"
              >
                {sessionMessage}
              </p>
            ) : null}

            {errorMessage ? (
              <p
                className="rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-sm text-rose-100"
                role="alert"
              >
                {errorMessage}
              </p>
            ) : null}

            <Button className="w-full" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Signing in..." : "Sign in"}
            </Button>
            <p className="text-center text-sm text-slate-500">
              New to KALYPTO?{" "}
              <Link className="font-medium text-cyan-300 hover:text-cyan-200" to="/signup">
                Create a workspace
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
