import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { ComingSoonBadge } from "../../lib/ui";

export function DashboardPage() {
  const { session, token, setSession } = useAuth();

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

  const logoutMutation = useMutation({
    mutationFn: async () => { if (token) await api.logout(token); },
    onSettled: () => setSession(null),
  });

  const shipments = shipmentsQuery.data ?? [];
  const preCount = shipments.filter((s) => s.shipment_stage === "pre_shipment").length;
  const postCount = shipments.filter((s) => s.shipment_stage === "post_shipment").length;
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
      {/* Welcome */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-slate-50">
          {user?.full_name ? `Welcome back, ${user.full_name.split(" ")[0]}` : "Dashboard"}
        </h2>
        <p className="mt-0.5 text-sm text-slate-500">{org?.name}</p>
      </div>

      {/* Stats */}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Total shipments" value={shipmentsQuery.isLoading ? "—" : String(shipments.length)} />
        <StatCard label="Pre-shipment" value={shipmentsQuery.isLoading ? "—" : String(preCount)} accent="text-indigo-300" />
        <StatCard label="Post-shipment" value={shipmentsQuery.isLoading ? "—" : String(postCount)} accent="text-emerald-300" />
        <StatCard
          label="Potential amount"
          value={
            discrepancyQuery.isLoading
              ? "—"
              : `INR ${(discrepancyQuery.data?.potential_amount ?? 0).toLocaleString("en-IN")}`
          }
          accent="text-amber-300"
        />
      </div>

      <Card className="mb-6 overflow-hidden border-cyan-300/20 bg-slate-950/80">
        <div className="h-1 bg-gradient-to-r from-cyan-300 via-emerald-300 to-amber-300" />
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>KALYPTO tool workspace</CardTitle>
              <CardDescription>
                HSN finder, compliance checker, export quote calculator, document builder,
                verifier, claims tracker, and alerts now live in one command center.
              </CardDescription>
            </div>
            <Link to="/tools">
              <Button>Open tools</Button>
            </Link>
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
        {/* Recent shipments */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Recent shipments</CardTitle>
              <Link to="/shipments" className="text-xs font-medium text-indigo-400 hover:text-indigo-300">
                View all →
              </Link>
            </div>
            <CardDescription>
              Each shipment walks through checklist → documents → verification report.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {shipmentsQuery.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
            {!shipmentsQuery.isLoading && shipments.length === 0 && (
              <div className="py-8 text-center">
                <p className="text-sm text-slate-500">No shipments yet.</p>
                <Link to="/shipments/new">
                  <Button className="mt-4" size="sm">+ Create first shipment</Button>
                </Link>
              </div>
            )}
            {recentShipments.length > 0 && (
              <div className="flex flex-col gap-2">
                {recentShipments.map((s) => (
                  <Link
                    key={s.id}
                    to={`/shipments/${s.id}`}
                    className="flex items-center justify-between rounded-lg border border-white/6 bg-slate-950/40 px-4 py-3 transition-colors hover:border-indigo-500/30 hover:bg-indigo-500/5"
                  >
                    <div>
                      <p className="text-sm font-medium text-slate-100">{s.product_name}</p>
                      <p className="mt-0.5 text-xs text-slate-500">
                        HSN {s.hsn_code} · {s.destination_country}
                      </p>
                    </div>
                    <span className={`text-xs font-medium ${s.shipment_stage === "pre_shipment" ? "text-indigo-300" : "text-emerald-300"}`}>
                      {s.shipment_stage === "pre_shipment" ? "Pre-shipment" : "Post-shipment"}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Account + quick action */}
        <div className="flex w-full flex-col gap-4 lg:w-64">
          <Card>
            <CardHeader><CardTitle>Account</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Row label="Name" value={user?.full_name ?? "—"} />
              <Row label="Email" value={user?.email ?? "—"} />
              <Row label="Role" value={role.replaceAll("_", " ")} />
              <Button className="mt-3 w-full" size="sm" variant="secondary" onClick={() => logoutMutation.mutate()}>
                {logoutMutation.isPending ? "Signing out…" : "Sign out"}
              </Button>
            </CardContent>
          </Card>
          <Link to="/shipments/new">
            <Button className="w-full">+ New shipment</Button>
          </Link>
        </div>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Discrepancy overview</CardTitle>
            <span className="text-xs text-slate-500">
              {discrepancyQuery.data?.total ?? 0} findings
            </span>
          </div>
          <CardDescription>
            Persisted deterministic findings from shipment reconciliation.
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
              className="mt-2 block rounded-lg border border-white/6 bg-slate-950/40 p-3 hover:border-indigo-500/30"
              key={item.id}
              to={`/shipments/${item.shipment_id}`}
            >
              <p className="text-sm font-medium text-slate-200">{item.message}</p>
              <p className="mt-1 text-xs capitalize text-slate-500">
                {item.severity} / {item.type.replaceAll("_", " ")}
              </p>
            </Link>
          ))}
          <p className="mt-3 text-xs text-slate-600">
            {discrepancyQuery.data?.disclaimer}
          </p>
        </CardContent>
      </Card>

      {/* Documentation assistant — gated */}
      <Card className="mt-4">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Documentation Assistant</CardTitle>
            <ComingSoonBadge />
          </div>
          <CardDescription>
            Ask about RoDTEP rates, Advance Authorisation, eBRC realization, and DGFT filing steps.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <p className="text-2xl" aria-hidden="true">📋</p>
            <p className="text-sm font-medium text-slate-300">Launching in a future update</p>
            <p className="max-w-sm text-sm text-slate-500">
              An AI assistant for DGFT regulations, ITC(HS) classification, and export documentation procedures.
            </p>
          </div>
        </CardContent>
      </Card>
    </DashboardShell>
  );
}

function StatCard({ label, value, accent = "text-slate-50" }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-white/8 bg-slate-900/70 px-4 py-4 backdrop-blur">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${accent}`}>{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium capitalize text-slate-200">{value}</span>
    </div>
  );
}
