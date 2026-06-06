import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@repo/ui";

import { AuthShell } from "../../components/layout/auth-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export function SignupPage() {
  const navigate = useNavigate();
  const { setSession } = useAuth();

  const mutation = useMutation({
    mutationFn: async (formData: FormData) =>
      api.register({
        full_name: String(formData.get("full_name") ?? ""),
        organization_name: String(formData.get("organization_name") ?? ""),
        email: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? "")
      }),
    onSuccess: (session) => {
      setSession(session);
      navigate("/", { replace: true });
    }
  });

  const errorMessage =
    mutation.isError && mutation.error instanceof Error ? mutation.error.message : null;

  return (
    <AuthShell
      eyebrow="Phase 0 onboarding"
      title="Create your organization and get an isolated workspace instantly."
      description="Signup provisions the tenant, assigns the owner role, and returns you to a protected dashboard shell without leaking data across organizations."
    >
      <Card>
        <CardHeader>
          <CardTitle>Create account</CardTitle>
          <CardDescription>We'll create both the owner user and the first organization.</CardDescription>
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
              <Label htmlFor="full_name">Full name</Label>
              <Input id="full_name" name="full_name" placeholder="Priya Shah" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="organization_name">Organization name</Label>
              <Input id="organization_name" name="organization_name" placeholder="Shah Exports LLP" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" name="email" placeholder="owner@shahexports.in" type="email" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" name="password" placeholder="At least 12 characters" type="password" required />
            </div>
            {errorMessage ? (
              <p className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                {errorMessage}
              </p>
            ) : null}
            <Button className="w-full" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating workspace..." : "Create workspace"}
            </Button>
            <p className="text-sm text-slate-400">
              Already set up?{" "}
              <Link className="text-cyan-300 hover:text-cyan-200" to="/login">
                Log in here
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
