import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@repo/ui";

import { AuthShell } from "../../components/layout/auth-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

type GoogleCredentialResponse = { credential?: string };

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
          }) => void;
          prompt: () => void;
        };
      };
    };
  }
}

function loadGoogleIdentityScript() {
  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }
  return new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>("script[data-google-identity]");
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Google login could not load.")), {
        once: true,
      });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.dataset.googleIdentity = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Google login could not load."));
    document.head.appendChild(script);
  });
}

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { session, setSession } = useAuth();
  const [clientError, setClientError] = useState<string | null>(null);
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const reason = (location.state as { reason?: string } | null)?.reason;
  const successMessage = (location.state as { message?: string } | null)?.message;
  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

  useEffect(() => {
    if (session) {
      navigate(from, { replace: true });
      return;
    }
    if (reason === "session-expired") {
      navigate("/login", { replace: true, state: { from } });
    }
  }, [from, navigate, reason, session]);

  const mutation = useMutation({
    mutationFn: async (formData: FormData) =>
      api.login({
        email: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? ""),
        otp_code: String(formData.get("otp_code") ?? "").trim() || undefined,
      }),
    onSuccess: (session) => {
      setSession(session);
      navigate(from, { replace: true });
    },
  });

  const googleMutation = useMutation({
    mutationFn: (idToken: string) => api.loginWithGoogle(idToken),
    onSuccess: (nextSession) => {
      setSession(nextSession);
      navigate(from, { replace: true });
    },
  });

  const handleGoogleLogin = async () => {
    setClientError(null);
    if (!googleClientId) {
      setClientError("Google login is not configured yet.");
      return;
    }
    try {
      await loadGoogleIdentityScript();
      window.google?.accounts.id.initialize({
        client_id: googleClientId,
        callback: (response) => {
          if (!response.credential) {
            setClientError("Google login could not be verified.");
            return;
          }
          googleMutation.mutate(response.credential);
        },
      });
      window.google?.accounts.id.prompt();
    } catch (error) {
      setClientError(userMessageForError(error));
    }
  };

  const errorMessage =
    clientError ??
    (mutation.isError ? userMessageForError(mutation.error) : null) ??
    (googleMutation.isError ? userMessageForError(googleMutation.error) : null);
  const sessionMessage =
    successMessage ??
    (reason === "session-expired" ? "Your session expired for security. Please sign in again." : null);
  const showVerifyLink = errorMessage?.toLowerCase().includes("not verified");

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
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="otp_code">Authenticator code</Label>
              <Input
                id="otp_code"
                name="otp_code"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="6-digit code if enabled"
              />
            </div>

            <Button
              className="w-full"
              variant="secondary"
              type="button"
              disabled={googleMutation.isPending}
              onClick={handleGoogleLogin}
            >
              {googleMutation.isPending ? "Checking Google..." : "Continue with Google"}
            </Button>

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
                {showVerifyLink ? (
                  <>
                    {" "}
                    <Link className="font-medium text-cyan-200 hover:text-cyan-100" to="/verify-email">
                      Verify your email
                    </Link>
                  </>
                ) : null}
              </p>
            ) : null}

            <Button className="w-full" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Signing in..." : "Sign in"}
            </Button>
            <p className="text-center text-sm text-slate-500">
              <Link className="font-medium text-cyan-300 hover:text-cyan-200" to="/forgot-password">
                Forgot password?
              </Link>
            </p>
            <p className="text-center text-sm text-slate-500">
              New to KALYPTO?{" "}
              <Link className="font-medium text-cyan-300 hover:text-cyan-200" to="/register">
                Create an account
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
