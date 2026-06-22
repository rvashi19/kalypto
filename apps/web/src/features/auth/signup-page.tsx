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
        password: String(formData.get("password") ?? ""),
      }),
    onSuccess: (session) => {
      setSession(session);
      navigate("/", { replace: true });
    },
  });

  const errorMessage =
    mutation.isError && mutation.error instanceof Error ? mutation.error.message : null;

  return (
    <AuthShell
      eyebrow="Indian export compliance"
      title="Your export documents, verified before they reach customs."
      description="Create a workspace for your organization and start auditing shipment documents in minutes."
    >
      <Card>
        <CardHeader>
          <CardTitle>Create workspace</CardTitle>
          <CardDescription>Set up your organization account to get started.</CardDescription>
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
              <Label htmlFor="full_name">Your name</Label>
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
                placeholder="At least 12 characters"
                required
              />
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
              {mutation.isPending ? "Creating workspace…" : "Create workspace"}
            </Button>
            <p className="text-center text-sm text-slate-500">
              Already set up?{" "}
              <Link className="text-indigo-400 hover:text-indigo-300" to="/login">
                Sign in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </AuthShell>
  );
}
