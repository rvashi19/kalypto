import { useMutation, useQuery } from "@tanstack/react-query";

import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export function DashboardPage() {
  const { session, token, setSession } = useAuth();

  const overviewQuery = useQuery({
    queryKey: ["dashboard-overview", token],
    queryFn: () => api.dashboardOverview(token!),
    enabled: Boolean(token)
  });

  const meQuery = useQuery({
    queryKey: ["current-user", token],
    queryFn: () => api.me(token!),
    enabled: Boolean(token)
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) {
        await api.logout(token);
      }
    },
    onSettled: () => setSession(null)
  });

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>Foundation status</CardTitle>
            <CardDescription>
              This dashboard is intentionally light for Phase 0, but the secure backbone is active.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-4 md:grid-cols-3">
              <StatusCard title="Authentication" value="Ready" caption="Register, login, logout, and owner membership bootstrapping." />
              <StatusCard title="Tenancy" value="Locked" caption="Repository queries are scoped by organization ID." />
              <StatusCard title="Audit" value="Live" caption="Requests and repository actions append to the audit trail." />
            </div>
            <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm text-cyan-100">
              {overviewQuery.isLoading ? "Loading dashboard overview..." : overviewQuery.data?.message}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Account snapshot</CardTitle>
            <CardDescription>Useful sanity checks before Phase 1 ingestion and reconciliation.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <SnapshotRow label="User" value={meQuery.data?.user.full_name ?? session?.user.full_name ?? "Owner"} />
            <SnapshotRow label="Email" value={meQuery.data?.user.email ?? session?.user.email ?? ""} />
            <SnapshotRow
              label="Organization"
              value={meQuery.data?.organization.name ?? session?.organization.name ?? ""}
            />
            <SnapshotRow label="Role" value={meQuery.data?.membership.role ?? session?.membership.role ?? ""} />
            <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4 text-slate-300">
              Demo seed account after `docker compose up`:
              <div className="mt-2 font-mono text-xs text-slate-400">
                demo@example.com / DemoPassword123!
              </div>
            </div>
            <Button className="w-full" variant="secondary" onClick={() => logoutMutation.mutate()}>
              {logoutMutation.isPending ? "Signing out..." : "Sign out"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </DashboardShell>
  );
}

function StatusCard({ title, value, caption }: { title: string; value: string; caption: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-50">{value}</p>
      <p className="mt-2 text-sm text-slate-500">{caption}</p>
    </div>
  );
}

function SnapshotRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-4 py-3">
      <span className="text-slate-400">{label}</span>
      <span className="font-medium text-slate-100">{value}</span>
    </div>
  );
}
