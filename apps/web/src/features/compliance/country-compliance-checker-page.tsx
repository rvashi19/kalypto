import type {
  ComplianceCheckRequestV1,
  ComplianceCheckResponseV1,
  ReviewQueueItem,
  SourceRegistryCreateRequest,
  SourceRegistryResponse,
} from "@repo/shared";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Select,
  Textarea,
} from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useLogout } from "../../lib/use-logout";

const COUNTRIES = [
  "India",
  "Canada",
  "USA",
  "UK",
  "Netherlands/EU",
  "United Arab Emirates",
  "Saudi Arabia",
];
const CATEGORIES = [
  "food/agri",
  "beverages",
  "textiles",
  "spices",
  "dry fruits",
  "chemicals",
  "plastic/packaging",
];
const SOURCE_TYPES = ["html", "pdf", "xlsx", "csv"];

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

function TextField({
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
    <Field label={label}>
      <Input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </Field>
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
    <Field label={label}>
      <Select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </Select>
    </Field>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-base font-semibold text-ink">{children}</h2>;
}

function QuestionList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-xs font-semibold text-ink-2">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink">
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
      <Alert tone="warning" title="No verified requirement found">
        No verified official requirement found in the current knowledge base or official-source
        search.
      </Alert>
    );
  }

  if (result.status === "retrieval_queued") {
    const job = jobQuery.data;
    return (
      <Card>
        <CardHeader>
          <SectionTitle>Official-source retrieval in progress</SectionTitle>
          <p className="text-sm text-ink-2">
            Results will require review before becoming approved guidance.
          </p>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-ink">
          <p>
            Status: <Badge tone="info">{job?.status ?? "queued"}</Badge>
          </p>
          {job && (
            <p className="text-xs text-ink-2">
              Pages fetched: {job.pages_fetched} · Snapshots: {job.snapshots_created} · Extracted
              (pending review): {job.requirements_extracted}
            </p>
          )}
          {job?.message && <p className="text-xs text-ink-2">{job.message}</p>}
          <Button
            variant="secondary"
            loading={jobQuery.isFetching}
            onClick={() => jobQuery.refetch()}
          >
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
          <SectionTitle>Result</SectionTitle>
          <p className="text-sm text-ink-2">
            Confidence: {result.confidence_label} ({result.confidence_score}) ·{" "}
            {result.answer_summary}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {Object.entries(GROUP_LABELS).map(([key, label]) => {
            const cards = result.requirements[key] ?? [];
            if (!cards.length) return null;
            return (
              <div key={key}>
                <h3 className="text-sm font-semibold text-ink">{label}</h3>
                <ul className="mt-1 space-y-2">
                  {cards.map((c, i) => (
                    <li key={i} className="rounded-panel border border-line bg-surface p-3 text-sm">
                      <p className="text-ink">{c.detail}</p>
                      {c.source_url && (
                        <a
                          className="mt-1 inline-block text-xs text-brand underline"
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
            <SectionTitle>Official source evidence</SectionTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {result.sources.map((s) => (
              <div key={s.source_url}>
                <a
                  className="text-brand underline"
                  href={s.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {s.source_name}
                </a>
                <span className="ml-2 text-xs text-ink-2">
                  {s.last_checked_date ? `last retrieved ${s.last_checked_date}` : "date unknown"}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {result.warnings.length > 0 && (
        <Alert tone="warning" title="Check before relying on this result">
          <ul className="list-disc space-y-1 pl-4">
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Alert>
      )}
      <p className="text-xs text-ink-2">{result.disclaimer}</p>
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
  authority_level: "official",
  product_categories: ["textiles"],
  refresh_frequency_days: 30,
  is_active: true,
  notes: "",
};

function AdminSourceManager() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SourceRegistryCreateRequest>(SOURCE_DEFAULT);
  const [allowedDomainsText, setAllowedDomainsText] = useState("");
  const [lastSourceJobId, setLastSourceJobId] = useState<string | null>(null);

  const sourcesQuery = useQuery({
    queryKey: ["compliance-sources"],
    queryFn: () => api.listComplianceSources(token!),
    enabled: Boolean(token),
  });

  const createMut = useMutation({
    mutationFn: () => api.createComplianceSource(form, token!),
    onSuccess: () => {
      setForm(SOURCE_DEFAULT);
      setAllowedDomainsText("");
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

  const refreshSourceMut = useMutation({
    mutationFn: (sourceId: string) => api.refreshComplianceSource(sourceId, token!),
    onSuccess: (job) => {
      setLastSourceJobId(job.id);
      queryClient.invalidateQueries({ queryKey: ["compliance-sources"] });
      queryClient.invalidateQueries({ queryKey: ["compliance-review-queue"] });
    },
  });

  const sourceJobQuery = useQuery({
    queryKey: ["compliance-source-refresh-job", lastSourceJobId],
    queryFn: () => api.retrievalJob(lastSourceJobId!, token!),
    enabled: Boolean(token && lastSourceJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    },
  });

  const sources: SourceRegistryResponse[] = sourcesQuery.data ?? [];
  const sourceJob = sourceJobQuery.data;

  function updateAllowedDomains(value: string) {
    setAllowedDomainsText(value);
    setForm((current) => ({
      ...current,
      allowed_domains: value
        .split(",")
        .map((domain) => domain.trim())
        .filter(Boolean),
    }));
  }

  return (
    <Card>
      <CardHeader>
        <SectionTitle>Official sources (admin)</SectionTitle>
        <p className="text-sm text-ink-2">
          Register government or regulatory source URLs. Only whitelisted official domains are
          accepted.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => seedMut.mutate()} loading={seedMut.isPending}>
            Seed official sources
          </Button>
          <Button
            variant="secondary"
            onClick={() => refreshMut.mutate()}
            loading={refreshMut.isPending}
          >
            Refresh due sources
          </Button>
        </div>
        {seedMut.data && (
          <Alert tone="success">
            Seeded {seedMut.data.created} new source(s), updated {seedMut.data.updated}, skipped{" "}
            {seedMut.data.skipped}.
          </Alert>
        )}
        {refreshMut.data && (
          <Alert tone="success">
            Ran {refreshMut.data.jobs_run} job(s) - {refreshMut.data.snapshots_created} snapshot(s)
            - {refreshMut.data.requirements_extracted} extracted (pending review).
          </Alert>
        )}
        {(seedMut.error || refreshMut.error || refreshSourceMut.error) && (
          <Alert tone="danger" title="Source action failed">
            {userMessageForError(seedMut.error ?? refreshMut.error ?? refreshSourceMut.error)}
          </Alert>
        )}
        {sourceJob && (
          <Alert tone="info" title={`Latest source refresh: ${sourceJob.status}`}>
            <p>
              Fetched {sourceJob.pages_fetched} page/file(s) - checksum{" "}
              {sourceJob.checksum_status ?? "pending"} - parser {sourceJob.parser_used ?? "pending"}
            </p>
            <p>
              Extracted {sourceJob.requirements_extracted} requirement(s);{" "}
              {sourceJob.pending_review_count} pending review.
            </p>
            {sourceJob.error_message && <p className="text-danger-fg">{sourceJob.error_message}</p>}
          </Alert>
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
        <div className="grid gap-2 sm:grid-cols-2">
          <SelectField
            label="Source type"
            value={form.source_type ?? "html"}
            options={SOURCE_TYPES}
            onChange={(v) =>
              setForm((c) => ({
                ...c,
                source_type: v as SourceRegistryCreateRequest["source_type"],
              }))
            }
          />
          <TextField
            label="Refresh frequency days"
            value={String(form.refresh_frequency_days ?? 30)}
            placeholder="30"
            onChange={(v) =>
              setForm((c) => ({ ...c, refresh_frequency_days: Number.parseInt(v, 10) || 30 }))
            }
          />
        </div>
        <TextField
          label="Authority name"
          value={form.authority_name}
          placeholder="Canada Border Services Agency"
          onChange={(v) => setForm((c) => ({ ...c, authority_name: v }))}
        />
        <TextField
          label="Source name"
          value={form.source_name}
          placeholder="CBSA import requirements"
          onChange={(v) => setForm((c) => ({ ...c, source_name: v }))}
        />
        <TextField
          label="Official source URL"
          value={form.base_url}
          placeholder="https://www.cbsa-asfc.gc.ca/import/..."
          onChange={(v) => setForm((c) => ({ ...c, base_url: v }))}
        />
        <TextField
          label="Extra allowed domains (optional, comma separated)"
          value={allowedDomainsText}
          placeholder="official-domain.gov, regulator.example"
          onChange={updateAllowedDomains}
        />
        <Field label="Notes (optional)">
          <Textarea
            value={form.notes ?? ""}
            placeholder="What this source covers and when to use it"
            onChange={(e) => setForm((c) => ({ ...c, notes: e.target.value }))}
          />
        </Field>
        <div className="flex flex-wrap items-center gap-4 text-sm text-ink">
          <span>Authority level: official</span>
          <div className="flex items-center gap-2">
            <input
              id="source-active"
              type="checkbox"
              className="h-4 w-4 accent-brand"
              checked={form.is_active ?? true}
              onChange={(e) => setForm((c) => ({ ...c, is_active: e.target.checked }))}
            />
            <label htmlFor="source-active">Active source</label>
          </div>
        </div>
        <Button
          onClick={() => createMut.mutate()}
          loading={createMut.isPending}
          disabled={!form.base_url || !form.authority_name}
        >
          Add official source
        </Button>
        {createMut.isError && (
          <Alert tone="danger" title="Could not add the source">
            {userMessageForError(createMut.error)}
          </Alert>
        )}

        {sources.length > 0 && (
          <div className="space-y-2 pt-2">
            <h3 className="text-sm font-semibold text-ink">Registered sources</h3>
            {sources.map((s) => (
              <div
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-panel border border-line bg-surface p-3 text-xs text-ink-2"
              >
                <div>
                  <p className="text-ink">
                    {s.country} - {s.product_categories.join(", ") || "all"} - {s.source_type}
                    {!s.is_active && " - inactive"}
                  </p>
                  <a
                    className="text-brand underline"
                    href={s.base_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {s.source_name}
                  </a>
                  <p>
                    {s.authority_name} - {s.authority_level} - refresh every{" "}
                    {s.refresh_frequency_days} day(s)
                  </p>
                  <p>Last checked: {s.last_checked_at ?? "never"}</p>
                  {s.notes && <p>{s.notes}</p>}
                </div>
                <Button
                  variant="secondary"
                  onClick={() => refreshSourceMut.mutate(s.id)}
                  loading={refreshSourceMut.isPending && refreshSourceMut.variables === s.id}
                  disabled={refreshSourceMut.isPending || !s.is_active}
                >
                  Refresh this source
                </Button>
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
      action === "approve" ? api.approveRequirement(id, token!) : api.rejectRequirement(id, token!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["compliance-review-queue"] }),
  });

  const items: ReviewQueueItem[] = queue.data ?? [];

  return (
    <Card>
      <CardHeader>
        <SectionTitle>Pending requirement review</SectionTitle>
        <p className="text-sm text-ink-2">
          AI-extracted requirements stay pending until an admin approves the source evidence.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {queue.isError && (
          <Alert tone="danger" title="Could not load the review queue">
            {userMessageForError(queue.error)}
          </Alert>
        )}
        {decide.isError && (
          <Alert tone="danger" title="Could not record the decision">
            {userMessageForError(decide.error)}
          </Alert>
        )}
        {queue.isSuccess && items.length === 0 && (
          <EmptyState title="Nothing to review" description="No pending requirements to review." />
        )}
        {items.map((item) => (
          <div
            key={item.requirement_id}
            className="rounded-panel border border-line bg-surface p-3"
          >
            <p className="text-sm text-ink">{item.detail}</p>
            <p className="mt-1 text-xs text-ink-2">
              {item.country} · {item.category} · {item.requirement_type} · confidence{" "}
              {item.confidence_score}
            </p>
            <a
              className="text-xs text-brand underline"
              href={item.source_url}
              target="_blank"
              rel="noreferrer"
            >
              {item.source_name}
            </a>
            {item.evidence_excerpts.map((ex, i) => (
              <p
                key={i}
                className="mt-1 border-l-2 border-line-strong pl-2 text-xs italic text-ink-2"
              >
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
  const { session, token } = useAuth();
  const [form, setForm] = useState<ComplianceCheckRequestV1>(DEFAULT_FORM);
  const isAdmin = session?.membership.role === "owner";

  const mutation = useMutation({
    mutationFn: () => api.complianceCheck(form, token!),
  });

  const logoutMutation = useLogout();

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <PageHeader
        title="Country compliance checker"
        breadcrumbs={[{ label: "Compliance" }, { label: "Country checker" }]}
        meta={
          <span>
            See destination-country documents, certificates, labels, inspections, licences and
            restrictions, backed by official-source evidence only.
          </span>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <SectionTitle>Check requirements</SectionTitle>
            <p className="text-sm text-ink-2">Official evidence is the source of truth.</p>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                mutation.mutate();
              }}
            >
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
              <TextField
                label="HSN code"
                value={form.hsn_code ?? ""}
                onChange={(v) => setForm((c) => ({ ...c, hsn_code: v }))}
              />
              <TextField
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
              <Button type="submit" loading={mutation.isPending} disabled={!token}>
                Check compliance
              </Button>
              {mutation.isError && (
                <Alert tone="danger" title="Could not check compliance">
                  {userMessageForError(mutation.error)}
                </Alert>
              )}
            </form>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {mutation.data ? (
            <ResultView result={mutation.data} />
          ) : (
            <EmptyState
              title="No result yet"
              description="Run a check. Official-source retrieval can be started automatically."
            />
          )}
          {isAdmin && <AdminSourceManager />}
          {isAdmin && <AdminReviewQueue />}
        </div>
      </div>
    </DashboardShell>
  );
}
