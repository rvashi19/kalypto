import type { ComplianceCheckerRequest, ComplianceCheckerResponse } from "@repo/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const DEFAULT_FORM: ComplianceCheckerRequest = {
  product: "Mango fruit beverage",
  hsn_code: "200989",
  destination_country: "Canada",
  category: "beverages",
  details: {
    retail_or_bulk: "retail",
    packaging_type: "bottle",
    processed_state: "processed",
  },
};

export function CompliancePage() {
  const { session, token, setSession } = useAuth();
  const [form, setForm] = useState<ComplianceCheckerRequest>(DEFAULT_FORM);

  const optionsQuery = useQuery({
    queryKey: ["compliance-options", token],
    queryFn: () => api.complianceOptions(token!),
    enabled: Boolean(token),
  });

  const mutation = useMutation({
    mutationFn: async () => api.askComplianceChecker(form, token!),
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <div className="mb-6">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-indigo-400">
          Source-backed assistant
        </p>
        <h2 className="mt-1 text-xl font-semibold text-slate-50">
          Country Compliance Requirement Checker
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Check destination-country documents, certificates, labeling, restrictions, inspection
          needs, and buyer-side questions from approved compliance evidence.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle>Check requirements</CardTitle>
            <CardDescription>
              V0 scope is intentionally limited to approved, cached evidence.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field
              label="Product"
              value={form.product}
              onChange={(value) => setForm((current) => ({ ...current, product: value }))}
            />
            <Field
              label="HSN"
              value={form.hsn_code ?? ""}
              onChange={(value) => setForm((current) => ({ ...current, hsn_code: value }))}
            />
            <SelectField
              label="Destination"
              value={form.destination_country}
              options={optionsQuery.data?.countries ?? ["Canada", "United Arab Emirates", "UK"]}
              onChange={(value) =>
                setForm((current) => ({ ...current, destination_country: value }))
              }
            />
            <SelectField
              label="Category"
              value={form.category}
              options={optionsQuery.data?.categories ?? ["beverages", "dry fruits", "spices", "textiles"]}
              onChange={(value) => setForm((current) => ({ ...current, category: value }))}
            />
            <label className="block space-y-2 text-sm">
              <span className="text-slate-300">Extra details</span>
              <textarea
                className="min-h-28 w-full rounded-lg border border-white/8 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none focus:border-indigo-500/40"
                value={detailsToText(form.details)}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    details: textToDetails(event.target.value),
                  }))
                }
                placeholder="retail_or_bulk: retail"
              />
            </label>

            <Button
              className="w-full"
              disabled={mutation.isPending || !form.product.trim()}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? "Checking..." : "Check compliance"}
            </Button>

            {mutation.isError ? (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
                {mutation.error instanceof Error
                  ? mutation.error.message
                  : "The compliance checker is unavailable right now."}
              </div>
            ) : null}
          </CardContent>
        </Card>

        {mutation.data ? (
          <ComplianceResult result={mutation.data} />
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Result preview</CardTitle>
              <CardDescription>
                Results will show confidence, source links, last checked dates, and unresolved
                questions.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-xl border border-dashed border-white/10 bg-slate-950/40 p-8 text-center text-sm text-slate-500">
                Run a check to see source-backed compliance assistance.
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardShell>
  );
}

function ComplianceResult({ result }: { result: ComplianceCheckerResponse }) {
  const summary = result.sections.product_summary;
  const insufficient =
    result.status === "insufficient_verified_data" || result.status === "needs_review";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{result.confidence_level} confidence</CardTitle>
            <CardDescription>{result.confidence_explanation}</CardDescription>
          </div>
          <span className="rounded-full border border-white/8 bg-slate-950/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            {result.status.replaceAll("_", " ")}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {insufficient ? (
          <div className="rounded-lg border border-amber-400/25 bg-amber-400/10 p-3 text-sm text-amber-100">
            Insufficient verified data available.
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2">
          <Fact label="Product" value={summary.product} />
          <Fact label="HSN" value={summary.hsn ?? "Not confirmed"} />
          <Fact label="Destination" value={summary.destination} />
          <Fact label="Category" value={summary.category} />
        </div>

        {result.last_checked_date ? (
          <p className="text-xs text-slate-500">
            Latest approved source checked: {result.last_checked_date}
          </p>
        ) : null}

        <Section title="Required documents" values={result.sections.required_import_documents} />
        <Section title="Certificates" values={result.sections.certificates_required} />
        <Section title="Labeling" values={result.sections.labeling_requirements} />
        <Section title="Restrictions / prohibited alerts" values={result.sections.restriction_alerts} />
        <Section
          title="Inspection / testing"
          values={result.sections.inspection_testing_requirements}
        />
        <Section title="Buyer-side questions" values={result.sections.buyer_side_questions} />
        <Section title="Unresolved questions" values={result.unresolved_questions} />

        {result.sections.source_references.length ? (
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-200">Sources</p>
            {result.sections.source_references.map((source) => (
              <a
                className="block rounded-lg border border-white/8 bg-slate-950/50 p-3 text-sm text-indigo-200 underline-offset-4 hover:underline"
                href={source.source_url}
                key={`${source.source_name}-${source.source_url}`}
                rel="noreferrer"
                target="_blank"
              >
                <span className="font-medium">{source.source_name}</span>
                <span className="mt-1 block text-xs text-slate-500">
                  {source.source_authority_level} - last checked{" "}
                  {source.last_checked_date ?? "unknown"}
                  {source.expires_at ? ` - expires ${source.expires_at}` : ""}
                </span>
              </a>
            ))}
          </div>
        ) : null}

        <div className="rounded-lg border border-white/8 bg-slate-950/50 p-3 text-xs leading-6 text-slate-400">
          {result.disclaimer}
        </div>
      </CardContent>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/8 bg-slate-950/50 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-medium text-slate-100">{value}</p>
    </div>
  );
}

function Section({ title, values }: { title: string; values: string[] }) {
  if (!values.length) return null;

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-200">{title}</p>
      <ul className="space-y-2">
        {values.map((value, index) => (
          <li
            className="rounded-lg border border-white/8 bg-slate-950/40 p-3 text-sm text-slate-300"
            key={`${title}-${index}`}
          >
            {value}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block space-y-2 text-sm">
      <span className="text-slate-300">{label}</span>
      <input
        className="w-full rounded-lg border border-white/8 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none focus:border-indigo-500/40"
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
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="block space-y-2 text-sm">
      <span className="text-slate-300">{label}</span>
      <select
        className="w-full rounded-lg border border-white/8 bg-slate-950/70 px-3 py-2 text-slate-100 outline-none focus:border-indigo-500/40"
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
      .filter(([key]) => key),
  );
}
