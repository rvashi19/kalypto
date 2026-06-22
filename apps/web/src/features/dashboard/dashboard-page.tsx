import type { ComplianceCheckerRequest, ComplianceCheckerResponse } from "@repo/shared";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const DEFAULT_COMPLIANCE_FORM: ComplianceCheckerRequest = {
  product: "Mango fruit beverage",
  hsn_code: "200989",
  destination_country: "Canada",
  category: "beverages",
  details: {
    retail_or_bulk: "retail",
    packaging_type: "bottle",
    processed_state: "processed"
  }
};

export function DashboardPage() {
  const { session, token, setSession } = useAuth();
  const [question, setQuestion] = useState(
    "What is already live in this KALYPTO build, and what still comes in later phases?"
  );
  const [complianceForm, setComplianceForm] = useState<ComplianceCheckerRequest>(DEFAULT_COMPLIANCE_FORM);

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

  const complianceOptionsQuery = useQuery({
    queryKey: ["compliance-options", token],
    queryFn: () => api.complianceOptions(token!),
    enabled: Boolean(token)
  });

  const assistantMutation = useMutation({
    mutationFn: async () => api.askDocumentationAssistant(question, token!)
  });

  const complianceMutation = useMutation({
    mutationFn: async () => api.askComplianceChecker(complianceForm, token!)
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
            <CardDescription>Useful sanity checks before ingestion, reconciliation, and compliance workflows.</CardDescription>
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
          <CardTitle>Country Compliance Requirement Checker</CardTitle>
          <CardDescription>
            Ask destination-country compliance questions from stored, source-backed records.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            <Field
              label="Product"
              value={complianceForm.product}
              onChange={(value) => setComplianceForm((current) => ({ ...current, product: value }))}
            />
            <Field
              label="HSN"
              value={complianceForm.hsn_code ?? ""}
              onChange={(value) => setComplianceForm((current) => ({ ...current, hsn_code: value }))}
            />
            <SelectField
              label="Destination"
              value={complianceForm.destination_country}
              options={complianceOptionsQuery.data?.countries ?? ["Canada", "United Arab Emirates", "USA", "Netherlands/EU", "UK", "Saudi Arabia"]}
              onChange={(value) => setComplianceForm((current) => ({ ...current, destination_country: value }))}
            />
            <SelectField
              label="Category"
              value={complianceForm.category}
              options={complianceOptionsQuery.data?.categories ?? ["food/agri", "spices", "dry fruits", "beverages", "textiles"]}
              onChange={(value) => setComplianceForm((current) => ({ ...current, category: value }))}
            />
          </div>
          <textarea
            className="min-h-24 w-full rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-sm text-slate-100 outline-none ring-0 placeholder:text-slate-500 focus:border-cyan-400/40"
            value={detailsToText(complianceForm.details)}
            onChange={(event) =>
              setComplianceForm((current) => ({
                ...current,
                details: textToDetails(event.target.value)
              }))
            }
            placeholder="Extra details, one per line. Example: retail_or_bulk: retail"
          />
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p className="text-xs text-slate-500">
              The checker answers only from stored compliance records and always includes source references.
            </p>
            <Button
              onClick={() => complianceMutation.mutate()}
              disabled={complianceMutation.isPending || !complianceForm.product.trim()}
            >
              {complianceMutation.isPending ? "Checking..." : "Check requirements"}
            </Button>
          </div>
          {complianceMutation.isError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
              {complianceMutation.error instanceof Error
                ? complianceMutation.error.message
                : "The compliance checker is unavailable right now."}
            </div>
          ) : null}
          {complianceMutation.data ? <ComplianceResult result={complianceMutation.data} /> : null}
        </CardContent>
      </Card>

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
              The AI helper needs `XAI_API_KEY` on the API service. Core signup/login do not.
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

function ComplianceResult({ result }: { result: ComplianceCheckerResponse }) {
  return (
    <div className="space-y-4 rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm text-cyan-50">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-200">Result</p>
          <p className="mt-1 text-lg font-semibold">{result.confidence_level} confidence</p>
        </div>
        <span className="rounded-full border border-white/10 bg-slate-950/80 px-3 py-1 text-xs uppercase text-slate-300">
          {result.status.replace("_", " ")}
        </span>
      </div>
      <p className="text-slate-300">{result.confidence_explanation}</p>
      <pre className="max-h-[34rem] overflow-auto whitespace-pre-wrap rounded-xl border border-white/10 bg-slate-950/80 p-4 leading-7 text-slate-100">
        {result.answer}
      </pre>
      {result.follow_up_questions.length ? (
        <SectionList title="Follow-up questions" values={result.follow_up_questions} />
      ) : null}
      {result.sections.source_references.length ? (
        <div className="space-y-2">
          <p className="font-semibold text-slate-100">Sources</p>
          {result.sections.source_references.map((source) => (
            <a
              className="block rounded-xl border border-white/10 bg-slate-950/70 p-3 text-cyan-100 underline-offset-4 hover:underline"
              href={source.source_url}
              key={`${source.source_name}-${source.source_url}`}
              rel="noreferrer"
              target="_blank"
            >
              {source.source_name} Â· {source.last_scraped_date}
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SectionList({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="space-y-2">
      <p className="font-semibold text-slate-100">{title}</p>
      <ul className="space-y-2 text-slate-300">
        {values.map((value) => (
          <li className="rounded-xl border border-white/10 bg-slate-950/60 p-3" key={value}>
            {value}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="space-y-2 text-sm">
      <span className="text-slate-300">{label}</span>
      <input
        className="w-full rounded-xl border border-white/10 bg-slate-950/80 px-4 py-3 text-slate-100 outline-none focus:border-cyan-400/40"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-2 text-sm">
      <span className="text-slate-300">{label}</span>
      <select
        className="w-full rounded-xl border border-white/10 bg-slate-950/80 px-4 py-3 text-slate-100 outline-none focus:border-cyan-400/40"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
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

function detailsToText(details: ComplianceCheckerRequest["details"]) {
  return Object.entries(details ?? {})
    .map(([key, value]) => `${key}: ${value ?? ""}`)
    .join("\n");
}

function textToDetails(value: string) {
  return Object.fromEntries(
    value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [key, ...rest] = line.split(":");
        return [key.trim(), rest.join(":").trim()];
      })
      .filter(([key]) => key)
  );
}