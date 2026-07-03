import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@repo/ui";

import { AuthShell } from "../../components/layout/auth-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

function passwordPolicyError(password: string) {
  const missing = [];
  if (password.length < 12) missing.push("12 characters");
  if (!/[a-z]/.test(password)) missing.push("a lowercase letter");
  if (!/[A-Z]/.test(password)) missing.push("an uppercase letter");
  if (!/\d/.test(password)) missing.push("a number");
  if (!/[^A-Za-z0-9]/.test(password)) missing.push("a symbol");
  return missing.length ? `Password must include ${missing.join(", ")}.` : null;
}

export function SignupPage() {
  const navigate = useNavigate();
  const { session } = useAuth();
  const [clientError, setClientError] = useState<string | null>(null);

  useEffect(() => {
    if (session) {
      navigate("/tools", { replace: true });
    }
  }, [navigate, session]);

  const mutation = useMutation({
    mutationFn: async (formData: FormData) =>
      api.register({
        full_name: String(formData.get("full_name") ?? ""),
        email: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? ""),
        company_name: String(formData.get("company_name") ?? "") || undefined,
        country: String(formData.get("country") ?? "") || undefined,
      }),
    onSuccess: (response) => {
      navigate(`/verify-email?email=${encodeURIComponent(response.email)}`, {
        replace: true,
        state: { message: response.message },
      });
    },
  });

  const errorMessage = clientError ?? (mutation.isError ? userMessageForError(mutation.error) : null);

  return (
    <AuthShell
      eyebrow="Secure exporter onboarding"
      title="Create a verified account before any export data enters the workspace."
      description="KALYPTO verifies every owner email first, then opens the protected organization workspace after the OTP check passes."
    >
      <Card>
        <CardHeader>
          <CardTitle>Create your workspace</CardTitle>
          <CardDescription>We will email a 6-digit code before activating the account.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const formData = new FormData(event.currentTarget);
              const passwordError = passwordPolicyError(String(formData.get("password") ?? ""));
              if (passwordError) {
                setClientError(passwordError);
                return;
              }
              setClientError(null);
              mutation.mutate(formData);
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="full_name">Full name</Label>
              <Input id="full_name" name="full_name" placeholder="Priya Shah" required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="company_name">Company name</Label>
              <Input
                id="company_name"
                name="company_name"
                placeholder="Shah Exports LLP"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="country">Country</Label>
              <Input id="country" name="country" placeholder="India" />
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
                minLength={12}
                autoComplete="new-password"
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
              {mutation.isPending ? "Sending code..." : "Create account"}
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
