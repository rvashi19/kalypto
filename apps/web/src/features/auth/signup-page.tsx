import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@repo/ui";

import { AuthShell } from "../../components/layout/auth-shell";
import { api, userMessageForError } from "../../lib/api";
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
        password: String(formData.get("password") ?? ""),
      }),
    onSuccess: (session) => {
      setSession(session);
      navigate("/", { replace: true });
    },
  });

  const errorMessage = mutation.isError ? userMessageForError(mutation.error) : null;

  return (
    <AuthShell
      eyebrow="Secure exporter onboarding"
      title="Create a protected workspace for every shipment, document, and claim."
      description="Start with one organization account. KALYPTO provisions tenant isolation, owner access, and an audited workspace immediately."
    >
      <Card>
        <CardHeader>
          <CardTitle>Create your workspace</CardTitle>
          <CardDescription>Set up the owner account for your export organization.</CardDescription>
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
              <Label htmlFor="full_name">Full name</Label>
              <Input id="full_name" name="full_name" placeholder="Priya Shah" required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="organization_name">Organization name</Label>
              <Input
                id="organization_name"
                name="organization_name"
                placeholder="Shah Exports LLP"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">Work email</Label>
              <Input id="email" name="email" type="email" placeholder="owner@shahexports.in" required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="Use at least 12 characters"
                required
              />
            </div>

            {errorMessage ? (
              <p
                className="rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-sm text-rose-100"
                role="alert"
              >
                {errorMessage}
              </p>
            ) : null}

            <Button className="w-full" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Creating workspace..." : "Create workspace"}
            </Button>
            <p className="text-center text-sm text-slate-500">
              Already have an account?{" "}
              <Link className="font-medium text-cyan-300 hover:text-cyan-200" to="/login">
                Sign in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
