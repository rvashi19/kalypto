import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label } from "@repo/ui";

import { AuthShell } from "../../components/layout/auth-shell";
import { api, userMessageForError } from "../../lib/api";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const mutation = useMutation({
    mutationFn: (formData: FormData) => api.forgotPassword(String(formData.get("email") ?? "")),
    onSuccess: (response, formData) => {
      const email = String(formData.get("email") ?? "");
      navigate(`/reset-password?email=${encodeURIComponent(email)}`, {
        state: { message: response.message },
      });
    },
  });

  const errorMessage = mutation.isError ? userMessageForError(mutation.error) : null;

  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Reset access with a short-lived email code."
      description="Password reset codes are single-use and never stored in plain text."
    >
      <Card>
        <CardHeader>
          <CardTitle>Forgot password</CardTitle>
          <CardDescription>If an account exists for this email, a reset code has been sent.</CardDescription>
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
              <Input id="email" name="email" type="email" placeholder="owner@exportco.in" required />
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
              {mutation.isPending ? "Sending code..." : "Send reset code"}
            </Button>
            <p className="text-center text-sm text-slate-500">
              Remembered it?{" "}
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
