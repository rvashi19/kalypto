import type {
  ComplianceCheckRequestV1,
  ComplianceCheckResponseV1,
  ReviewQueueItem,
  SourceRegistryCreateRequest,
  SourceRegistryResponse,
} from "@repo/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { inputCls, selectCls } from "../../lib/ui";

const COUNTRIES = ["Canada", "USA", "UK", "Netherlands/EU", "United Arab Emirates", "Saudi Arabia"];
const CATEGORIES = ["food/agri", "beverages", "textiles", "spices", "dry fruits"];

const GROUP_LABELS: Record<string, string> = {
  documents: "Required Documents",
  labels: "Labels",
  certificates: "Certificates",
  inspections: "Inspections",
  licences: "Licences",
  restrictions: "Restrictions",
};

const DEFAULT_FORM: ComplianceCheckRequestV1 = {
  origin_country: "India",
  destination_country: "Canada",
  hsn_code: "200989",
  product_description: "Mango fruit beverage in retail bottles",
  product_category: "beverages",
  start_retrieval: true,
};

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="text-slate-300">{label}</span>
      <input
        className={inputCls}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
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
  onChange: (v: string) => void;
}) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="text-slate-300">{label}</span>
      <select className={selectCls} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

function QuestionList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-300">
        {items.map((q) => (
          <li key={q}>{q}</li>
        ))}
      </ul>
    </div>
  );
}

function ResultView({ result }: { result: ComplianceCheckResponseV1 }) {
  const { token } = useAuth();

  // Poll the retrieval job while it's in progress.
  const jobQuery = useQuery({
    queryKey: ["compliance-retrieval-job", result.retrieval_job_id],
    queryFn: () => api.retrievalJob(result.retrieval_job_id!, token!),
    enabled: Boolean(result.retrieval_job_id && token),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "queued" || s === "running" ? 3000 : false;
    },
  });

  if (result.status === "no_verified_source") {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-amber-300">
          No verified official requirement found in the current knowledge base or official-source
          search.
        </CardContent>
      </Card>
    );
  }

  if (result.status === "retrieval_queued") {
    const job = jobQuery.data;
    return (
      <Card>
        <CardHeader>
          <CardTitle>Official-source retrieval in progress</CardTitle>
          <CardDescription>
            Results will require review before becoming approved guidance.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-slate-300">
          <p>Status: {job?.status ?? "queued"}</p>
          {job && (
            <p className="text-xs text-slate-500">
              Pages fetched: {job.pages_fetched} · Snapshots: {job.snapshots_created} · Extracted
              (pending review): {job.requirements_extracted}
            </p>
          )}
          {job?.message && <p className="text-xs text-slate-500">{job.message}</p>}
          <Button variant="secondary" onClick={() => jobQuery.refetch()}>
            Refresh status
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Result</CardTitle>
          <CardDescription>
            Confidence: {result.confidence_label} ({result.confidence_score}) · {result.answer_summary}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {Object.entries(GROUP_LABELS).map(([key, label]) => {
            const cards = result.requirements[key] ?? [];
            if (!cards.length) return null;
            return (
              <div key={key}>
                <p className="text-xs font-semibold uppercase tracking-wide text-cyan-200">
                  {label}
                </p>
                <ul className="mt-1 space-y-2">
                  {cards.map((c, i) => (
                    <li key={i} className="rounded-lg border border-white/10 bg-slate-950/60 p-3 text-sm">
                      <p className="text-slate-100">{c.detail}</p>
                      {c.source_url && (
                        <a
                          className="mt-1 inline-block text-xs text-cyan-300 underline"
                          href={c.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {c.source_name ?? c.source_url}
                          {c.last_checked_date ? ` · checked ${c.last_checked_date}` : ""}
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
          <QuestionList title="Missing information" items={result.missing_questions} />
          <QuestionList title="Buyer-side questions" items={result.buyer_questions} />
          <QuestionList title="CHA / customs broker questions" items={result.cha_questions} />
        </CardContent>
      </Card>

      {result.sources.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Official source evidence</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {result.sources.map((s) => (
              <div key={s.source_url}>
                <a className="text-cyan-300 underline" href={s.source_url} target="_blank" rel="noreferrer">
                  {s.source_name}
                </a>
                <span className="ml-2 text-xs text-slate-500">
                  {s.last_checked_date ? `last retrieved ${s.last_checked_date}` : "date unknown"}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="space-y-1 py-4 text-xs text-slate-500">
          {result.warnings.map((w) => (
            <p key={w}>⚠ {w}</p>
          ))}
          <p className="pt-1 text-slate-400">{result.disclaimer}</p>
        </CardContent>
      </Card>
    </div>
  );
}

const SOURCE_DEFAULT: SourceRegistryCreateRequest = {
  country: "Canada",
  authority_name: "",
  source_name: "",
  base_url: "",
  allowed_domains: [],
  source_type: "html",
  product_categories: ["textiles"],
  refresh_frequency_days: 30,
};

function AdminSourceManager() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SourceRegistryCreateRequest>(SOURCE_DEFAULT);

  const sourcesQuery = useQuery({
    queryKey: ["compliance-sources"],
    queryFn: () => api.listComplianceSources(token!),
    enabled: Boolean(token),
  });

  const createMut = useMutation({
    mutationFn: () => api.createComplianceSource(form, token!),
    onSuccess: () => {
      setForm(SOURCE_DEFAULT);
      queryClient.invalidateQueries({ queryKey: ["compliance-sources"] });
    },
  });

  const seedMut = useMutation({
    mutationFn: () => api.seedComplianceSources(token!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["compliance-sources"] }),
  });

  const refreshMut = useMutation({
    mutationFn: () => api.refreshDueComplianceSources(token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["compliance-sources"] });
      queryClient.invalidateQueries({ queryKey: ["compliance-review-queue"] });
    },
  });

  const sources: SourceRegistryResponse[] = sourcesQuery.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Official sources (admin)</CardTitle>
        <CardDescription>
          Register the government/regulatory page or PDF to fetch. Only whitelisted official
          domains are accepted (e.g. cbsa-asfc.gc.ca, inspection.canada.ca, fda.gov, apeda.gov.in).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => seedMut.mutate()} disabled={seedMut.isPending}>
            {seedMut.isPending ? "Seeding…" : "Seed official sources"}
          </Button>
          <Button variant="secondary" onClick={() => refreshMut.mutate()} disabled={refreshMut.isPending}>
            {refreshMut.isPending ? "Refreshing…" : "Refresh due now"}
          </Button>
        </div>
        {seedMut.data && (
          <p className="text-xs text-emerald-300">
            Seeded {seedMut.data.created} new source(s) ({seedMut.data.skipped} already present).
          </p>
        )}
        {refreshMut.data && (
          <p className="text-xs text-emerald-300">
            Ran {refreshMut.data.jobs_run} job(s) · {refreshMut.data.snapshots_created} snapshot(s) ·{" "}
            {refreshMut.data.requirements_extracted} extracted (pending review).
          </p>
        )}
        <div className="grid gap-2 sm:grid-cols-2">
          <SelectField
            label="Country"
            value={form.country}
            options={COUNTRIES}
            onChange={(v) => setForm((c) => ({ ...c, country: v }))}
          />
          <SelectField
            label="Category"
            value={(form.product_categories ?? ["textiles"])[0] ?? "textiles"}
            options={CATEGORIES}
            onChange={(v) => setForm((c) => ({ ...c, product_categories: [v] }))}
          />
        </div>
        <Field
          label="Authority name"
          value={form.authority_name}
          placeholder="Canada Border Services Agency"
          onChange={(v) => setForm((c) => ({ ...c, authority_name: v }))}
        />
        <Field
          label="Source name"
          value={form.source_name}
          placeholder="CBSA import requirements"
          onChange={(v) => setForm((c) => ({ ...c, source_name: v }))}
        />
        <Field
          label="Official source URL"
          value={form.base_url}
          placeholder="https://www.cbsa-asfc.gc.ca/import/..."
          onChange={(v) => setForm((c) => ({ ...c, base_url: v }))}
        />
        <Button
          onClick={() => createMut.mutate()}
          disabled={createMut.isPending || !form.base_url || !form.authority_name}
        >
          {createMut.isPending ? "Adding…" : "Add official source"}
        </Button>
        {createMut.isError && (
          <p className="text-sm text-red-400">{userMessageForError(createMut.error)}</p>
        )}

        {sources.length > 0 && (
          <div className="space-y-1 pt-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Registered sources
            </p>
            {sources.map((s) => (
              <div key={s.id} className="text-xs text-slate-400">
                {s.country} · {s.product_categories.join(", ") || "all"} —{" "}
                <a className="text-cyan-300 underline" href={s.base_url} target="_blank" rel="noreferrer">
                  {s.source_name}
                </a>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AdminReviewQueue() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const queue = useQuery({
    queryKey: ["compliance-review-queue"],
    queryFn: () => api.complianceReviewQueue(token!),
    enabled: Boolean(token),
  });

  const decide = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      action === "approve"
        ? api.approveRequirement(id, token!)
        : api.rejectRequirement(id, token!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["compliance-review-queue"] }),
  });

  const items: ReviewQueueItem[] = queue.data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pending requirement review</CardTitle>
        <CardDescription>
          AI-extracted requirements stay pending until an admin approves the source evidence.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.length === 0 && (
          <p className="text-sm text-slate-500">No pending requirements to review.</p>
        )}
        {items.map((item) => (
          <div key={item.requirement_id} className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
            <p className="text-sm text-slate-100">{item.detail}</p>
            <p className="mt-1 text-xs text-slate-500">
              {item.country} · {item.category} · {item.requirement_type} · confidence{" "}
              {item.confidence_score}
            </p>
            <a className="text-xs text-cyan-300 underline" href={item.source_url} target="_blank" rel="noreferrer">
              {item.source_name}
            </a>
            {item.evidence_excerpts.map((ex, i) => (
              <p key={i} className="mt-1 border-l-2 border-slate-700 pl-2 text-xs italic text-slate-400">
                {ex}
              </p>
            ))}
            <div className="mt-2 flex gap-2">
              <Button
                onClick={() => decide.mutate({ id: item.requirement_id, action: "approve" })}
                disabled={decide.isPending}
              >
                Approve
              </Button>
              <Button
                variant="secondary"
                onClick={() => decide.mutate({ id: item.requirement_id, action: "reject" })}
                disabled={decide.isPending}
              >
                Reject
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function CountryComplianceCheckerPage() {
  const { session, token, setSession } = useAuth();
  const [form, setForm] = useState<ComplianceCheckRequestV1>(DEFAULT_FORM);
  const isAdmin = session?.membership.role === "owner";

  const mutation = useMutation({
    mutationFn: () => api.complianceCheck(form, token!),
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
        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-200">
          Source-backed assistant
        </p>
        <h2 className="mt-1 text-xl font-semibold text-slate-50">Country Compliance Checker</h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Enter your shipment details to see destination-country documents, certificates, labels,
          inspections, licences, restrictions, and buyer/CHA questions — backed by official-source
          evidence only.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle>Check requirements</CardTitle>
            <CardDescription>Official evidence is the source of truth.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <SelectField
              label="Origin country"
              value={form.origin_country}
              options={["India"]}
              onChange={(v) => setForm((c) => ({ ...c, origin_country: v }))}
            />
            <SelectField
              label="Destination country"
              value={form.destination_country}
              options={COUNTRIES}
              onChange={(v) => setForm((c) => ({ ...c, destination_country: v }))}
            />
            <Field
              label="HSN code"
              value={form.hsn_code ?? ""}
              onChange={(v) => setForm((c) => ({ ...c, hsn_code: v }))}
            />
            <Field
              label="Product description"
              value={form.product_description}
              onChange={(v) => setForm((c) => ({ ...c, product_description: v }))}
            />
            <SelectField
              label="Product category"
              value={form.product_category}
              options={CATEGORIES}
              onChange={(v) => setForm((c) => ({ ...c, product_category: v }))}
            />
            <Button onClick={() => mutation.mutate()} disabled={mutation.isPending || !token}>
              {mutation.isPending ? "Checking…" : "Check compliance"}
            </Button>
            {mutation.isError && (
              <p className="text-sm text-red-400">{userMessageForError(mutation.error)}</p>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          {mutation.data ? (
            <ResultView result={mutation.data} />
          ) : (
            <Card>
              <CardContent className="py-8 text-center text-sm text-slate-500">
                No approved compliance requirement found yet. Run a check — official-source
                retrieval can be started automatically.
              </CardContent>
            </Card>
          )}
          {isAdmin && <AdminSourceManager />}
          {isAdmin && <AdminReviewQueue />}
        </div>
      </div>
    </DashboardShell>
  );
}
