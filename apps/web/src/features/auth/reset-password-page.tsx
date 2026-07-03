import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@repo/ui";

import { AuthShell } from "../../components/layout/auth-shell";
import { api, userMessageForError } from "../../lib/api";

function passwordPolicyError(password: string) {
  const missing = [];
  if (password.length < 12) missing.push("12 characters");
  if (!/[a-z]/.test(password)) missing.push("a lowercase letter");
  if (!/[A-Z]/.test(password)) missing.push("an uppercase letter");
  if (!/\d/.test(password)) missing.push("a number");
  if (!/[^A-Za-z0-9]/.test(password)) missing.push("a symbol");
  return missing.length ? `Password must include ${missing.join(", ")}.` : null;
}

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [clientError, setClientError] = useState<string | null>(null);
  const stateMessage = (location.state as { message?: string } | null)?.message;

  const mutation = useMutation({
    mutationFn: (formData: FormData) =>
      api.resetPassword({
        email: String(formData.get("email") ?? ""),
        otp: String(formData.get("otp") ?? ""),
        new_password: String(formData.get("new_password") ?? ""),
      }),
    onSuccess: (response) => {
      navigate("/login", { replace: true, state: { message: response.message } });
    },
  });

  const errorMessage = useMemo(() => {
    if (clientError) return clientError;
    if (mutation.isError) return userMessageForError(mutation.error);
    return null;
  }, [clientError, mutation.error, mutation.isError]);

  return (
    <AuthShell
      eyebrow="Password reset"
      title="Set a new password after verifying your email code."
      description="A successful reset revokes all existing refresh tokens for the account."
    >
      <Card>
        <CardHeader>
          <CardTitle>Reset password</CardTitle>
          <CardDescription>
            {stateMessage ?? "If an account exists for this email, a reset code has been sent."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const formData = new FormData(event.currentTarget);
              const password = String(formData.get("new_password") ?? "");
              const confirm = String(formData.get("confirm_password") ?? "");
              const passwordError = passwordPolicyError(password);
              if (passwordError) {
                setClientError(passwordError);
                return;
              }
              if (password !== confirm) {
                setClientError("Passwords do not match.");
                return;
              }
              setClientError(null);
              mutation.mutate(formData);
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="otp">6-digit reset code</Label>
              <Input
                id="otp"
                name="otp"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                autoComplete="one-time-code"
                placeholder="123456"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new_password">New password</Label>
              <Input
                id="new_password"
                name="new_password"
                type="password"
                minLength={12}
                autoComplete="new-password"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm_password">Confirm password</Label>
              <Input
                id="confirm_password"
                name="confirm_password"
                type="password"
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
              {mutation.isPending ? "Resetting..." : "Reset password"}
            </Button>
            <p className="text-center text-sm text-slate-500">
              Need a new code?{" "}
              <Link className="font-medium text-cyan-300 hover:text-cyan-200" to="/forgot-password">
                Send reset code
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
