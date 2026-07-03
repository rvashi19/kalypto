import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@repo/ui";

import { AuthShell } from "../../components/layout/auth-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [cooldown, setCooldown] = useState(0);
  const stateMessage = (location.state as { message?: string } | null)?.message;

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(() => setCooldown((current) => Math.max(0, current - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [cooldown]);

  const verifyMutation = useMutation({
    mutationFn: (formData: FormData) =>
      api.verifyEmailOtp({
        email: String(formData.get("email") ?? ""),
        otp: String(formData.get("otp") ?? ""),
      }),
    onSuccess: (session) => {
      setSession(session);
      navigate("/tools", { replace: true });
    },
  });

  const resendMutation = useMutation({
    mutationFn: () => api.resendOtp({ email, purpose: "email_verification" }),
    onSuccess: () => setCooldown(60),
  });

  const errorMessage = useMemo(() => {
    if (verifyMutation.isError) return userMessageForError(verifyMutation.error);
    if (resendMutation.isError) return userMessageForError(resendMutation.error);
    return null;
  }, [resendMutation.error, resendMutation.isError, verifyMutation.error, verifyMutation.isError]);

  return (
    <AuthShell
      eyebrow="Email verification"
      title="Enter the code we sent before opening your workspace."
      description="The code is short-lived, single-use, and stored hashed on the server."
    >
      <Card>
        <CardHeader>
          <CardTitle>Verify your email</CardTitle>
          <CardDescription>
            {stateMessage ?? "We sent a verification code to your email. Enter it to activate your account."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              verifyMutation.mutate(new FormData(event.currentTarget));
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
              <Label htmlFor="otp">6-digit code</Label>
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

            {errorMessage ? (
              <p
                className="rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-sm text-rose-100"
                role="alert"
              >
                {errorMessage}
              </p>
            ) : null}

            <Button className="w-full" type="submit" disabled={verifyMutation.isPending}>
              {verifyMutation.isPending ? "Verifying..." : "Verify email"}
            </Button>
            <Button
              className="w-full"
              variant="secondary"
              type="button"
              disabled={!email || cooldown > 0 || resendMutation.isPending}
              onClick={() => resendMutation.mutate()}
            >
              {cooldown > 0
                ? `Resend code in ${cooldown}s`
                : resendMutation.isPending
                  ? "Sending..."
                  : "Resend code"}
            </Button>
            <p className="text-center text-sm text-slate-500">
              Already verified?{" "}
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
