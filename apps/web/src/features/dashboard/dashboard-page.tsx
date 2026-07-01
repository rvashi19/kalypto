import { useMutation, useQuery } from "@tanstack/react-query";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";
import { useState } from "react";
import { Link } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { AiBadge } from "../../lib/ui";

export function DashboardPage() {
  const { session, token, setSession } = useAuth();
  const [assistantQuestion, setAssistantQuestion] = useState(
    "What should I verify before my next export shipment?",
  );

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

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });

  const shipments = shipmentsQuery.data ?? [];
  const preCount = shipments.filter((shipment) => shipment.shipment_stage === "pre_shipment").length;
  const postCount = shipments.filter((shipment) => shipment.shipment_stage === "post_shipment").length;
  const recentShipments = shipments.slice(0, 3);

  const user = meQuery.data?.user ?? session?.user;
  const org = meQuery.data?.organization ?? session?.organization;
  const role = meQuery.data?.membership.role ?? session?.membership.role ?? "";

  return (
    <DashboardShell
      organizationName={org?.name ?? "Workspace"}
      role={role}
      onLogout={() => logoutMutation.mutate()}
    >
      <section className="mb-6 overflow-hidden rounded-3xl border border-white/10 bg-slate-900/75 p-6 shadow-2xl shadow-slate-950/20">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200">
              Export assurance overview
            </p>
            <h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-[-0.035em] text-white md:text-4xl">
              {user?.full_name
                ? `Welcome back, ${user.full_name.split(" ")[0]}.`
                : "Welcome to your KALYPTO workspace."}
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-400">
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
          accent="text-cyan-200"
        />
        <StatCard
          label="Post-shipment"
          value={shipmentsQuery.isLoading ? "-" : String(postCount)}
          accent="text-emerald-300"
        />
        <StatCard
          label="Money at risk"
          value={
            discrepancyQuery.isLoading
              ? "-"
              : `INR ${(discrepancyQuery.data?.potential_amount ?? 0).toLocaleString("en-IN")}`
          }
          accent="text-amber-300"
        />
      </div>

      <Card className="mb-6 overflow-hidden border-cyan-300/20 bg-slate-900/80">
        <div className="h-px bg-gradient-to-r from-transparent via-cyan-200/50 to-transparent" />
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
                  Continue document generation, verification, or reconciliation from the shipment record.
                </CardDescription>
              </div>
              <Link to="/shipments" className="text-xs font-semibold text-cyan-300 hover:text-cyan-200">
                View all
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {shipmentsQuery.isLoading ? <p className="text-sm text-slate-500">Loading shipments...</p> : null}
            {!shipmentsQuery.isLoading && shipments.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/50 py-8 text-center">
                <p className="text-sm text-slate-400">No shipments yet.</p>
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
                    className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 transition-colors hover:border-cyan-300/30 hover:bg-cyan-300/5"
                  >
                    <div>
                      <p className="text-sm font-medium text-slate-100">
                        {shipment.product_name}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        HSN {shipment.hsn_code} / {shipment.destination_country}
                      </p>
                    </div>
                    <span
                      className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                        shipment.shipment_stage === "pre_shipment"
                          ? "border-cyan-300/20 bg-cyan-300/10 text-cyan-100"
                          : "border-emerald-300/20 bg-emerald-300/10 text-emerald-200"
                      }`}
                    >
                      {shipment.shipment_stage === "pre_shipment" ? "Pre-shipment" : "Post-shipment"}
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
          <Card className="border-amber-300/20 bg-amber-300/10">
            <CardContent className="pt-5">
              <p className="text-sm font-semibold text-amber-100">Decision-support mode</p>
              <p className="mt-2 text-xs leading-5 text-amber-100/75">
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
              <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs text-slate-400">
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
                className="mt-2 block rounded-2xl border border-white/10 bg-slate-950/50 p-3 transition hover:border-cyan-300/30"
                key={item.id}
                to={`/shipments/${item.shipment_id}`}
              >
                <p className="text-sm font-medium text-slate-200">{item.message}</p>
                <p className="mt-1 text-xs capitalize text-slate-500">
                  {item.severity} / {item.type.replaceAll("_", " ")}
                </p>
              </Link>
            ))}
            <p className="mt-3 text-xs leading-5 text-slate-600">{discrepancyQuery.data?.disclaimer}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle>Documentation Assistant</CardTitle>
              <AiBadge />
            </div>
            <CardDescription>
              Ask workflow questions. Legal, tax, and customs certainty still requires your
              CA, CHA, or customs broker.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div
                className={`rounded-xl border px-3 py-2 text-sm ${
                  assistantStatusQuery.data?.configured
                    ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-100"
                    : "border-amber-400/20 bg-amber-400/10 text-amber-100"
                }`}
              >
                {assistantStatusQuery.data?.message ?? "Checking AI helper status..."}
              </div>
              <textarea
                className="min-h-24 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3.5 py-3 text-sm text-slate-100 outline-none focus:ring-2 focus:ring-cyan-300/50"
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
                <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm leading-6 text-slate-300">
                  {assistantMutation.data.answer}
                </div>
              ) : null}
              {assistantMutation.isError ? (
                <p className="rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-sm text-rose-100">
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
  accent = "text-slate-50",
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/75 px-4 py-4 shadow-xl shadow-slate-950/10 backdrop-blur">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold tracking-[-0.02em] ${accent}`}>{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2">
      <span className="text-slate-500">{label}</span>
      <span className="truncate font-medium capitalize text-slate-200">{value}</span>
    </div>
  );
}
