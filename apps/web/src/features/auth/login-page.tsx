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
        password: String(formData.get("password") ?? ""),
      }),
    onSuccess: (session) => {
      setSession(session);
      navigate(from, { replace: true });
    },
  });

  const errorMessage =
    mutation.isError && mutation.error instanceof Error ? mutation.error.message : null;

  return (
    <AuthShell
      eyebrow="Indian export compliance"
      title="Catch document errors before they cost you."
      description="AI-powered audit of your export documents — catch discrepancies, estimate incentives, and submit with confidence."
    >
      <Card>
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>Enter your organization account to continue.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              mutation.mutate(new FormData(e.currentTarget));
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" name="email" type="email" placeholder="owner@exportco.in" required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" name="password" type="password" placeholder="Your password" required />
            </div>

            {errorMessage && (
              <p
                className="flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-500/8 px-3 py-2 text-sm text-rose-300"
                role="alert"
              >
                <span aria-hidden="true">✕</span> {errorMessage}
              </p>
            )}

            <Button className="w-full" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-center text-sm text-slate-500">
              No account?{" "}
              <Link className="text-indigo-400 hover:text-indigo-300" to="/signup">
                Create your workspace
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
