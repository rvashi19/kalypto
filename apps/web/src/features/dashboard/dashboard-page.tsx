import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
} from "@repo/ui";
import { useState } from "react";
import { Link } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useLogout } from "../../lib/use-logout";
import { AiBadge } from "../../lib/ui";

export function DashboardPage() {
  const { session, token, setSession } = useAuth();
  const [assistantQuestion, setAssistantQuestion] = useState(
    "What should I verify before my next export shipment?"
  );
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [twoFactorSetup, setTwoFactorSetup] = useState<{
    secret: string;
    otpauth_uri: string;
  } | null>(null);

  const shipmentsQuery = useQuery({
    queryKey: ["shipments", token],
    queryFn: () => api.listShipments(token!),
    enabled: Boolean(token),
  });

  const meQuery = useQuery({
    queryKey: ["current-user", token],
    queryFn: () => api.me(token!),
    enabled: Boolean(token),
  });

  const discrepancyQuery = useQuery({
    queryKey: ["discrepancy-dashboard", token],
    queryFn: () => api.discrepancyDashboard(token!),
    enabled: Boolean(token),
  });

  const assistantStatusQuery = useQuery({
    queryKey: ["documentation-assistant-status", token],
    queryFn: () => api.documentationAssistantStatus(token!),
    enabled: Boolean(token),
  });

  const assistantMutation = useMutation({
    mutationFn: () => api.askDocumentationAssistant(assistantQuestion, token!),
  });

  const logoutMutation = useLogout();

  const setupTwoFactorMutation = useMutation({
    mutationFn: () => api.setupTwoFactor(token!),
    onSuccess: setTwoFactorSetup,
  });

  const enableTwoFactorMutation = useMutation({
    mutationFn: () => api.enableTwoFactor(twoFactorCode, token!),
    onSuccess: async (currentSession) => {
      setSession(currentSession);
      setTwoFactorCode("");
      setTwoFactorSetup(null);
      await meQuery.refetch();
    },
  });

  const disableTwoFactorMutation = useMutation({
    mutationFn: () => api.disableTwoFactor(twoFactorCode, token!),
    onSuccess: async (currentSession) => {
      setSession(currentSession);
      setTwoFactorCode("");
      setTwoFactorSetup(null);
      await meQuery.refetch();
    },
  });

  const shipments = shipmentsQuery.data ?? [];
  const preCount = shipments.filter(
    (shipment) => shipment.shipment_stage === "pre_shipment"
  ).length;
  const postCount = shipments.filter(
    (shipment) => shipment.shipment_stage === "post_shipment"
  ).length;
  const recentShipments = shipments.slice(0, 3);

  const user = meQuery.data?.user ?? session?.user;
  const org = meQuery.data?.organization ?? session?.organization;
  const role = meQuery.data?.membership.role ?? session?.membership.role ?? "";
  const twoFactorEnabled = Boolean(user?.two_factor_enabled);
  const twoFactorError =
    setupTwoFactorMutation.error || enableTwoFactorMutation.error || disableTwoFactorMutation.error;

  return (
    <DashboardShell
      organizationName={org?.name ?? "Workspace"}
      role={role}
      onLogout={() => logoutMutation.mutate()}
    >
      <section className="mb-6 overflow-hidden rounded-card border border-line bg-surface p-6 shadow-card ">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold text-brand">Export assurance overview</p>
            <h1 className="mt-3 max-w-3xl text-2xl font-semibold tracking-tight text-ink md:text-3xl">
              {user?.full_name
                ? `Welcome back, ${user.full_name.split(" ")[0]}.`
                : "Welcome to your KALYPTO workspace."}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-ink-2">
              Monitor shipment readiness, claim exposure, compliance evidence, and AI-assisted
              document checks from one tenant-isolated workspace.
            </p>
          </div>
          <Link to="/shipments/new">
            <Button>Create shipment</Button>
          </Link>
        </div>
      </section>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Total shipments"
          value={shipmentsQuery.isLoading ? "-" : String(shipments.length)}
        />
        <StatCard
          label="Pre-shipment"
          value={shipmentsQuery.isLoading ? "-" : String(preCount)}
          accent="text-brand"
        />
        <StatCard
          label="Post-shipment"
          value={shipmentsQuery.isLoading ? "-" : String(postCount)}
          accent="text-success-fg"
        />
        <StatCard
          label="Money at risk"
          value={
            discrepancyQuery.isLoading
              ? "-"
              : `INR ${(discrepancyQuery.data?.potential_amount ?? 0).toLocaleString("en-IN")}`
          }
          accent="text-warning-fg"
        />
      </div>

      <Card className="mb-6 overflow-hidden border-brand bg-surface">
        <div className="h-px bg-surface from-transparent  to-transparent" />
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Assurance toolkit</CardTitle>
              <CardDescription>
                HSN finder, country compliance checker, quote calculator, document builder,
                verifier, claims tracker, and alerts are available from the tools workspace.
              </CardDescription>
            </div>
            <Link to="/tools">
              <Button>Open tools</Button>
            </Link>
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle>Recent shipments</CardTitle>
                <CardDescription>
                  Continue document generation, verification, or reconciliation from the shipment
                  record.
                </CardDescription>
              </div>
              <Link to="/shipments" className="text-xs font-semibold text-brand hover:text-brand">
                View all
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {shipmentsQuery.isLoading ? (
              <p className="text-sm text-ink-2">Loading shipments...</p>
            ) : null}
            {!shipmentsQuery.isLoading && shipments.length === 0 ? (
              <div className="rounded-card border border-dashed border-line bg-surface py-8 text-center">
                <p className="text-sm text-ink-2">No shipments yet.</p>
                <Link to="/shipments/new">
                  <Button className="mt-4" size="sm">
                    Create first shipment
                  </Button>
                </Link>
              </div>
            ) : null}
            {recentShipments.length > 0 ? (
              <div className="flex flex-col gap-2">
                {recentShipments.map((shipment) => (
                  <Link
                    key={shipment.id}
                    to={`/shipments/${shipment.id}`}
                    className="flex items-center justify-between rounded-card border border-line bg-surface px-4 py-3 transition-colors hover:border-brand hover:bg-brand-soft"
                  >
                    <div>
                      <p className="text-sm font-medium text-ink">{shipment.product_name}</p>
                      <p className="mt-0.5 text-xs text-ink-2">
                        HSN {shipment.hsn_code} / {shipment.destination_country}
                      </p>
                    </div>
                    <span
                      className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                        shipment.shipment_stage === "pre_shipment"
                          ? "border-brand bg-brand-soft text-brand"
                          : "border-success-border bg-success-bg text-success-fg"
                      }`}
                    >
                      {shipment.shipment_stage === "pre_shipment"
                        ? "Pre-shipment"
                        : "Post-shipment"}
                    </span>
                  </Link>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Account</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Row label="Name" value={user?.full_name ?? "-"} />
              <Row label="Email" value={user?.email ?? "-"} />
              <Row label="Role" value={role.replaceAll("_", " ")} />
              <Row label="2FA" value={twoFactorEnabled ? "enabled" : "off"} />
              <div className="rounded-panel border border-line bg-surface p-3">
                {twoFactorSetup ? (
                  <div className="space-y-2">
                    <Label htmlFor="two_factor_code">Authenticator code</Label>
                    <p className="break-all rounded-lg border border-brand bg-brand-soft px-2 py-1 font-mono text-xs text-brand">
                      {twoFactorSetup.secret}
                    </p>
                    <Input
                      id="two_factor_code"
                      inputMode="numeric"
                      value={twoFactorCode}
                      onChange={(event) => setTwoFactorCode(event.target.value)}
                      placeholder="6-digit code"
                    />
                    <Button
                      className="w-full"
                      size="sm"
                      onClick={() => enableTwoFactorMutation.mutate()}
                      disabled={enableTwoFactorMutation.isPending || twoFactorCode.length < 6}
                    >
                      {enableTwoFactorMutation.isPending ? "Enabling..." : "Enable 2FA"}
                    </Button>
                  </div>
                ) : twoFactorEnabled ? (
                  <div className="space-y-2">
                    <Label htmlFor="disable_two_factor_code">Authenticator code</Label>
                    <Input
                      id="disable_two_factor_code"
                      inputMode="numeric"
                      value={twoFactorCode}
                      onChange={(event) => setTwoFactorCode(event.target.value)}
                      placeholder="6-digit code"
                    />
                    <Button
                      className="w-full"
                      size="sm"
                      variant="secondary"
                      onClick={() => disableTwoFactorMutation.mutate()}
                      disabled={disableTwoFactorMutation.isPending || twoFactorCode.length < 6}
                    >
                      {disableTwoFactorMutation.isPending ? "Disabling..." : "Disable 2FA"}
                    </Button>
                  </div>
                ) : (
                  <Button
                    className="w-full"
                    size="sm"
                    variant="secondary"
                    onClick={() => setupTwoFactorMutation.mutate()}
                    disabled={setupTwoFactorMutation.isPending}
                  >
                    {setupTwoFactorMutation.isPending ? "Creating secret..." : "Set up 2FA"}
                  </Button>
                )}
                {twoFactorError ? (
                  <p className="mt-2 text-xs text-danger-fg">
                    {userMessageForError(twoFactorError)}
                  </p>
                ) : null}
              </div>
              <Button
                className="mt-3 w-full"
                size="sm"
                variant="secondary"
                onClick={() => logoutMutation.mutate()}
              >
                {logoutMutation.isPending ? "Signing out..." : "Sign out"}
              </Button>
            </CardContent>
          </Card>
          <Card className="border-warning-border bg-warning-bg">
            <CardContent className="pt-5">
              <p className="text-sm font-semibold text-warning-fg">Decision-support mode</p>
              <p className="mt-2 text-xs leading-5 text-warning-fg">
                Rates, HSN suggestions, and compliance guidance must be verified by an operator,
                CHA, CA, or customs broker before filing.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Discrepancy overview</CardTitle>
              <span className="rounded-full border border-line px-2.5 py-1 text-xs text-ink-2">
                {discrepancyQuery.data?.total ?? 0} findings
              </span>
            </div>
            <CardDescription>
              Deterministic findings from shipment reconciliation, including lock-risk signals.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-3">
              <Row label="Critical" value={String(discrepancyQuery.data?.critical ?? 0)} />
              <Row label="Warnings" value={String(discrepancyQuery.data?.warning ?? 0)} />
              <Row label="Lock risk" value={String(discrepancyQuery.data?.lock_risk ?? 0)} />
            </div>
            {discrepancyQuery.data?.items.slice(0, 5).map((item) => (
              <Link
                className="mt-2 block rounded-card border border-line bg-surface p-3 transition hover:border-brand"
                key={item.id}
                to={`/shipments/${item.shipment_id}`}
              >
                <p className="text-sm font-medium text-ink">{item.message}</p>
                <p className="mt-1 text-xs capitalize text-ink-2">
                  {item.severity} / {item.type.replaceAll("_", " ")}
                </p>
              </Link>
            ))}
            <p className="mt-3 text-xs leading-5 text-ink-3">{discrepancyQuery.data?.disclaimer}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Documentation Assistant</CardTitle>
              <AiBadge />
            </div>
            <CardDescription>
              Ask workflow questions. Legal, tax, and customs certainty still requires your CA, CHA,
              or customs broker.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div
                className={`rounded-panel border px-3 py-2 text-sm ${
                  assistantStatusQuery.data?.configured
                    ? "border-success-border bg-success-bg text-success-fg"
                    : "border-warning-border bg-warning-bg text-warning-fg"
                }`}
              >
                {assistantStatusQuery.data?.message ?? "Checking AI helper status..."}
              </div>
              <textarea
                className="min-h-24 w-full rounded-panel border border-line bg-surface px-3.5 py-3 text-sm text-ink outline-none focus:ring-2 focus:ring-brand"
                value={assistantQuestion}
                onChange={(event) => setAssistantQuestion(event.target.value)}
              />
              <Button
                disabled={
                  assistantMutation.isPending ||
                  !assistantQuestion.trim() ||
                  assistantStatusQuery.data?.configured === false
                }
                onClick={() => assistantMutation.mutate()}
              >
                {assistantMutation.isPending ? "Asking..." : "Ask assistant"}
              </Button>
              {assistantMutation.data ? (
                <div className="rounded-card border border-line bg-surface p-4 text-sm leading-6 text-ink">
                  {assistantMutation.data.answer}
                </div>
              ) : null}
              {assistantMutation.isError ? (
                <p className="rounded-panel border border-danger-border bg-danger-bg px-3 py-2 text-sm text-danger-fg">
                  {userMessageForError(assistantMutation.error)}
                </p>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}

function StatCard({
  label,
  value,
  accent = "text-ink",
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-card border border-line bg-surface px-4 py-4 shadow-card  backdrop-blur">
      <p className="text-xs font-semibold text-ink-2">{label}</p>
      <p className={`mt-2 text-2xl font-semibold tracking-[-0.02em] ${accent}`}>{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-panel border border-line bg-surface px-3 py-2">
      <span className="text-ink-2">{label}</span>
      <span className="truncate font-medium capitalize text-ink">{value}</span>
    </div>
  );
}
