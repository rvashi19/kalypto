import { useMutation } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@repo/ui";

import { AuthShell } from "../../components/layout/auth-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setSession } = useAuth();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const mutation = useMutation({
    mutationFn: async (formData: FormData) =>
      api.login({
        email: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? "")
      }),
    onSuccess: (session) => {
      setSession(session);
      navigate(from, { replace: true });
    }
  });

  const errorMessage =
    mutation.isError && mutation.error instanceof Error ? mutation.error.message : null;

  return (
    <AuthShell
      eyebrow="Secure exporter workspace"
      title="Recover incentive leakage without exposing tenant data."
      description="Start in the clean Phase 0 shell: email/password auth, organization-scoped access, and an audit-ready backend for the workflows we'll add next."
    >
      <Card>
        <CardHeader>
          <CardTitle>Log in</CardTitle>
          <CardDescription>Use your organization account to enter the dashboard.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              mutation.mutate(new FormData(event.currentTarget));
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" name="email" placeholder="owner@exportco.in" type="email" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" name="password" placeholder="Minimum 12 characters" type="password" required />
            </div>
            {errorMessage ? (
              <p className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                {errorMessage}
              </p>
            ) : null}
            <Button className="w-full" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Signing in..." : "Log in"}
            </Button>
            <p className="text-sm text-slate-400">
              Need an account?{" "}
              <Link className="text-cyan-300 hover:text-cyan-200" to="/signup">
                Create your organization
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
