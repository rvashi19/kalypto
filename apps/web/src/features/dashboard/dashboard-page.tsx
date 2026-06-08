import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

export function DashboardPage() {
  const { session, token, setSession } = useAuth();
  const [question, setQuestion] = useState(
    "What is already live in this KALYPTO build, and what still comes in later phases?"
  );

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

  const assistantStatusQuery = useQuery({
    queryKey: ["documentation-assistant-status", token],
    queryFn: () => api.documentationAssistantStatus(token!),
    enabled: Boolean(token)
  });

  const assistantMutation = useMutation({
    mutationFn: async () => api.askDocumentationAssistant(question, token!)
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
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>AI Documentation Helper</CardTitle>
          <CardDescription>
            Ask about the current KALYPTO build, onboarding steps, or what is and is not live yet.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4 text-sm text-slate-300">
            {assistantStatusQuery.isLoading
              ? "Checking AI helper status..."
              : assistantStatusQuery.data?.message}
          </div>
          <textarea
            className="min-h-32 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-slate-100 outline-none ring-0 placeholder:text-slate-500 focus:border-cyan-400/40"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask what is live, how to use the app, or what still needs manual filing."
          />
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p className="text-xs text-slate-500">
              The AI helper needs `OPENAI_API_KEY` on the API service. Core signup/login do not.
            </p>
            <Button
              onClick={() => assistantMutation.mutate()}
              disabled={assistantMutation.isPending || !question.trim()}
            >
              {assistantMutation.isPending ? "Thinking..." : "Ask helper"}
            </Button>
          </div>
          {assistantMutation.isError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
              {assistantMutation.error instanceof Error
                ? assistantMutation.error.message
                : "The AI documentation helper is unavailable right now."}
            </div>
          ) : null}
          {assistantMutation.data ? (
            <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm leading-7 text-cyan-50">
              <p className="mb-2 text-xs uppercase tracking-[0.2em] text-cyan-200">
                Answer via {assistantMutation.data.model}
              </p>
              <p>{assistantMutation.data.answer}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>
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
