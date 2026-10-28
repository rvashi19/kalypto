import type {
  DocumentExtractedFieldResponse,
  DocumentVerificationIssueResponse,
  DocumentVerificationRunCreate,
  DocumentVerificationRunResponse,
} from "@repo/shared";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  EmptyState,
  Field,
  Input,
  PageHeader,
  QueryState,
  type Tone,
} from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useLogout } from "../../lib/use-logout";

const EMPTY_FORM: DocumentVerificationRunCreate = {
  title: "Shipment document audit",
  reference_number: "",
  origin_country: "India",
  destination_country: "",
  hsn_code: "",
  product_description: "",
};

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;

export function DocumentVerifierPage() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const { session, token } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<DocumentVerificationRunCreate>(EMPTY_FORM);
  const [files, setFiles] = useState<File[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<DocumentVerificationIssueResponse | null>(
    null
  );

  const runsQuery = useQuery({
    queryKey: ["document-verifier-runs", token],
    queryFn: () => api.listDocumentVerificationRuns(token!),
    enabled: Boolean(token),
  });

  const runQuery = useQuery({
    queryKey: ["document-verifier-run", runId, token],
    queryFn: () => api.getDocumentVerificationRun(runId!, token!),
    enabled: Boolean(token && runId),
  });

  const createRunMutation = useMutation({
    mutationFn: () => api.createDocumentVerificationRun(form, token!),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["document-verifier-runs"] });
      navigate(`/document-verifier/${run.id}`);
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => api.uploadVerifierDocuments(runId!, files, token!),
    onSuccess: () => {
      setFiles([]);
      queryClient.invalidateQueries({ queryKey: ["document-verifier-run", runId] });
    },
  });

  const extractMutation = useMutation({
    mutationFn: () => api.extractVerifierRun(runId!, token!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["document-verifier-run", runId] }),
  });

  const verifyMutation = useMutation({
    mutationFn: () => api.verifyVerifierRun(runId!, token!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["document-verifier-run", runId] }),
  });

  const issueActionMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "resolve" | "ignore" }) =>
      action === "resolve"
        ? api.resolveVerifierIssue(id, token!)
        : api.ignoreVerifierIssue(id, token!),
    onSuccess: () => {
      setSelectedIssue(null);
      queryClient.invalidateQueries({ queryKey: ["document-verifier-run", runId] });
    },
  });

  const pdfMutation = useMutation({
    mutationFn: () => api.downloadVerifierReportPdf(runId!, token!),
  });

  const logoutMutation = useLogout();

  const run = runQuery.data;
  const runs = runsQuery.data ?? [];
  const issuesBySeverity = useMemo(() => groupIssues(run?.issues ?? []), [run]);
  const fieldsByDocument = useMemo(() => groupFields(run), [run]);

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <PageHeader
        title="AI Document Verifier"
        breadcrumbs={[{ label: "Audit" }, { label: "Document verifier" }]}
        meta={
          <span>
            Compare shipment documents before filing or claiming. Based on uploaded documents and
            source-backed KALYPTO data; verify with your CHA/customs broker before filing.
          </span>
        }
        actions={
          runId ? (
            <Link to="/document-verifier">
              <Button variant="secondary">New run</Button>
            </Link>
          ) : undefined
        }
      />

      {!runId ? (
        <div className="grid gap-5 lg:grid-cols-[420px_1fr]">
          <Card>
            <CardHeader>
              <SectionTitle>Create verification run</SectionTitle>
              <CardDescription>
                Upload shipment documents to compare fields before customs filing or incentive
                claims.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  createRunMutation.mutate();
                }}
              >
                <TextField
                  label="Title"
                  value={form.title}
                  onChange={(title) => setForm({ ...form, title })}
                />
                <TextField
                  label="Reference number"
                  mono
                  value={form.reference_number ?? ""}
                  onChange={(reference_number) => setForm({ ...form, reference_number })}
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <TextField
                    label="Origin"
                    value={form.origin_country ?? ""}
                    onChange={(origin_country) => setForm({ ...form, origin_country })}
                  />
                  <TextField
                    label="Destination"
                    value={form.destination_country ?? ""}
                    onChange={(destination_country) => setForm({ ...form, destination_country })}
                  />
                </div>
                <TextField
                  label="HSN"
                  mono
                  value={form.hsn_code ?? ""}
                  onChange={(hsn_code) => setForm({ ...form, hsn_code })}
                />
                <TextField
                  label="Product"
                  value={form.product_description ?? ""}
                  onChange={(product_description) => setForm({ ...form, product_description })}
                />
                <Button
                  type="submit"
                  className="w-full"
                  loading={createRunMutation.isPending}
                  disabled={!form.title.trim()}
                >
                  Create run
                </Button>
                {createRunMutation.error ? <ErrorBox error={createRunMutation.error} /> : null}
              </form>
            </CardContent>
          </Card>
          <RunList runs={runs} loading={runsQuery.isLoading} />
        </div>
      ) : null}

      {runId ? (
        runQuery.isLoading ? (
          <QueryState isLoading isError={false}>
            {null}
          </QueryState>
        ) : run ? (
          <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
            <div className="space-y-5">
              <RunSummary run={run} />
              <UploadPanel
                files={files}
                onFiles={setFiles}
                uploading={uploadMutation.isPending}
                error={uploadMutation.error}
                onUpload={() => uploadMutation.mutate()}
              />
              <ActionPanel
                run={run}
                extracting={extractMutation.isPending}
                verifying={verifyMutation.isPending}
                downloading={pdfMutation.isPending}
                extractError={extractMutation.error}
                verifyError={verifyMutation.error}
                pdfError={pdfMutation.error}
                onExtract={() => extractMutation.mutate()}
                onVerify={() => verifyMutation.mutate()}
                onDownload={() => pdfMutation.mutate()}
              />
            </div>
            <div className="space-y-5">
              <ScoreCard run={run} />
              <RequestedDocumentsPanel run={run} />
              <DocumentsPanel run={run} />
              <FieldsPanel fieldsByDocument={fieldsByDocument} />
              <IssuesPanel
                issuesBySeverity={issuesBySeverity}
                selectedIssue={selectedIssue}
                busy={issueActionMutation.isPending}
                onSelect={setSelectedIssue}
                onResolve={(id) => issueActionMutation.mutate({ id, action: "resolve" })}
                onIgnore={(id) => issueActionMutation.mutate({ id, action: "ignore" })}
              />
            </div>
          </div>
        ) : (
          <Alert tone="danger" title="Verification run was not found." />
        )
      ) : null}
    </DashboardShell>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-base font-semibold text-ink">{children}</h2>;
}

function TextField({
  label,
  value,
  mono,
  onChange,
}: {
  label: string;
  value: string;
  mono?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label}>
      <Input
        className={mono ? "font-mono" : undefined}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  );
}

function RunList({ runs, loading }: { runs: DocumentVerificationRunResponse[]; loading: boolean }) {
  return (
    <Card>
      <CardHeader>
        <SectionTitle>Recent verification runs</SectionTitle>
        <CardDescription>Open a run to upload, extract, verify, and review issues.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <QueryState
          isLoading={loading}
          isError={false}
          isEmpty={!runs.length}
          empty={<EmptyState title="No document verification runs yet" />}
        >
          {null}
        </QueryState>
        {runs.map((run) => (
          <Link
            key={run.id}
            to={`/document-verifier/${run.id}`}
            className="block rounded-panel border border-line bg-surface p-4 transition hover:border-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-ink">{run.title}</p>
                <p className="mt-1 text-xs text-ink-2">
                  <span className="font-mono">{run.reference_number || "No reference"}</span> /{" "}
                  {run.status}
                </p>
              </div>
              <span className="text-sm tabular-nums text-brand">{run.issues.length} issues</span>
            </div>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}

function RunSummary({ run }: { run: DocumentVerificationRunResponse }) {
  return (
    <Card>
      <CardHeader>
        <SectionTitle>{run.title}</SectionTitle>
        <CardDescription className="font-mono">
          {run.reference_number || "No reference number"}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        <Metric label="Status" value={run.status.replaceAll("_", " ")} />
        <Metric label="Documents" value={String(run.documents.length)} />
        <Metric label="Fields" value={String(run.fields.length)} />
        <Metric
          label="Open issues"
          value={String(run.issues.filter((i) => i.status === "open").length)}
        />
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-panel border border-line bg-surface-2 p-3">
      <p className="text-xs font-semibold text-ink-2">{label}</p>
      <p className="mt-1 font-semibold capitalize text-ink">{value}</p>
    </div>
  );
}

function UploadPanel({
  files,
  uploading,
  error,
  onFiles,
  onUpload,
}: {
  files: File[];
  uploading: boolean;
  error: unknown;
  onFiles: (files: File[]) => void;
  onUpload: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <SectionTitle>Upload documents</SectionTitle>
        <CardDescription>Accepted: PDF, XLSX, CSV, JPG, JPEG, PNG.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Field label="Documents">
          <input
            multiple
            type="file"
            accept=".pdf,.xlsx,.csv,.jpg,.jpeg,.png"
            onChange={(event) => onFiles(Array.from(event.target.files ?? []))}
            className="w-full rounded-panel border border-line bg-surface p-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          />
        </Field>
        {files.length ? (
          <p className="text-xs text-ink-2">{files.map((file) => file.name).join(", ")}</p>
        ) : (
          <p className="text-xs text-ink-2">No documents selected.</p>
        )}
        <Button className="w-full" loading={uploading} disabled={!files.length} onClick={onUpload}>
          Upload documents
        </Button>
        {error ? <ErrorBox error={error} /> : null}
      </CardContent>
    </Card>
  );
}

function ActionPanel({
  run,
  extracting,
  verifying,
  downloading,
  extractError,
  verifyError,
  pdfError,
  onExtract,
  onVerify,
  onDownload,
}: {
  run: DocumentVerificationRunResponse;
  extracting: boolean;
  verifying: boolean;
  downloading: boolean;
  extractError: unknown;
  verifyError: unknown;
  pdfError: unknown;
  onExtract: () => void;
  onVerify: () => void;
  onDownload: () => void;
}) {
  const hasDocs = run.documents.length > 0;
  const readyToVerify =
    hasDocs && run.documents.every((doc) => doc.extraction_status === "extracted");
  const needsReverify =
    run.overall_score != null && run.documents.some((doc) => doc.extraction_status === "pending");
  return (
    <Card>
      <CardHeader>
        <SectionTitle>Audit actions</SectionTitle>
        <CardDescription>Extract fields first, then run verification.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {needsReverify ? (
          <Alert tone="warning">
            New documents uploaded since the last verification. Extract fields and re-run
            verification to update the score.
          </Alert>
        ) : null}
        <Button className="w-full" loading={extracting} disabled={!hasDocs} onClick={onExtract}>
          Extract fields
        </Button>
        <Button className="w-full" loading={verifying} disabled={!readyToVerify} onClick={onVerify}>
          Run verification
        </Button>
        <Button
          className="w-full"
          variant="secondary"
          loading={downloading}
          disabled={!run.report}
          onClick={onDownload}
        >
          Download report PDF
        </Button>
        {extractError ? <ErrorBox error={extractError} /> : null}
        {verifyError ? <ErrorBox error={verifyError} /> : null}
        {pdfError ? <ErrorBox error={pdfError} /> : null}
      </CardContent>
    </Card>
  );
}

const READINESS_TONES: Record<string, Tone> = {
  ready_for_manual_review: "success",
  needs_minor_review: "info",
  needs_corrections: "warning",
  high_risk_do_not_file_without_review: "danger",
  waiting_for_required_documents: "info",
};

function scoreColor(score: number): string {
  if (score >= 90) return "text-success-fg";
  if (score >= 75) return "text-info-fg";
  if (score >= 50) return "text-warning-fg";
  return "text-danger-fg";
}

function ScoreCard({ run }: { run: DocumentVerificationRunResponse }) {
  if (run.overall_score == null) {
    return (
      <Card>
        <CardHeader>
          <SectionTitle>Document Verification Score</SectionTitle>
          <CardDescription>
            Score not calculated yet. Upload documents, extract fields, then run verification.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }
  const breakdown = run.score_breakdown ?? {};
  const counts = run.issue_counts ?? {};
  const categories: Array<{ key: string; label: string }> = [
    { key: "document_completeness", label: "Document Completeness" },
    { key: "field_consistency", label: "Field Consistency" },
    { key: "extraction_confidence", label: "Extraction Confidence" },
    { key: "claim_filing_risk", label: "Claim/Filing Risk" },
  ];
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <SectionTitle>Document Verification Score</SectionTitle>
            <CardDescription>
              Filing-readiness estimate.
              {run.last_verified_at
                ? ` Last verified ${new Date(run.last_verified_at).toLocaleString()}.`
                : ""}
            </CardDescription>
          </div>
          <div className="text-right">
            <p className={`text-4xl font-bold tabular-nums ${scoreColor(run.overall_score)}`}>
              {run.overall_score}
              <span className="text-base font-medium text-ink-2">/100</span>
            </p>
            <p className="mt-1 text-xs text-ink-2">{run.score_label}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {run.readiness_status ? (
          <Badge tone={READINESS_TONES[run.readiness_status] ?? "neutral"} className="text-sm">
            {run.readiness_label ?? run.readiness_status.replaceAll("_", " ")}
          </Badge>
        ) : null}
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {categories.map((category) => {
            const value = breakdown[category.key];
            return (
              <div key={category.key} className="rounded-panel border border-line bg-surface-2 p-3">
                <p className="text-xs font-semibold text-ink-2">{category.label}</p>
                <p
                  className={`mt-1 text-xl font-bold tabular-nums ${value != null ? scoreColor(value) : "text-ink-2"}`}
                >
                  {value ?? "-"}
                </p>
              </div>
            );
          })}
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          {(["critical", "high", "medium", "low", "info"] as const).map((severity) => (
            <Badge key={severity} className="capitalize">
              {severity}: {counts[severity] ?? 0}
            </Badge>
          ))}
        </div>
        {run.score_explanation ? (
          <p className="rounded-panel border border-line bg-surface p-3 text-sm text-ink">
            {run.score_explanation}
          </p>
        ) : null}
        {run.recommended_next_actions?.length ? (
          <div>
            <p className="mb-2 text-xs font-semibold text-ink-2">Recommended next actions</p>
            <ul className="space-y-1 text-sm text-ink">
              {run.recommended_next_actions.map((action) => (
                <li key={action} className="flex gap-2">
                  <span className="text-brand">→</span>
                  {action}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <p className="text-xs italic text-ink-2">
          This score estimates document consistency based on uploaded files and source-backed
          KALYPTO checks. Manual review with a CHA/customs broker is still required.
        </p>
      </CardContent>
    </Card>
  );
}

const PRIORITY_TONES: Record<string, Tone> = {
  critical: "danger",
  high: "warning",
  medium: "info",
  low: "neutral",
};

function RequestedDocumentsPanel({ run }: { run: DocumentVerificationRunResponse }) {
  const requested = run.requested_documents ?? [];
  if (!requested.length) return null;
  const missing = requested.filter((doc) => doc.status === "missing");
  const uploaded = requested.filter((doc) => doc.status !== "missing");
  return (
    <Card>
      <CardHeader>
        <SectionTitle>Documents needed for better verification</SectionTitle>
        <CardDescription>
          {missing.length
            ? `${missing.length} document(s) missing. Upload them above and re-run verification.`
            : "All expected documents are present. Re-run verification after any new upload."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {missing.map((doc) => (
          <div key={doc.document_type} className="rounded-panel border border-line bg-surface p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-ink">{doc.label}</p>
              <div className="flex gap-2">
                <Badge tone={PRIORITY_TONES[doc.priority] ?? "neutral"}>{doc.priority}</Badge>
                <Badge>{doc.required_for}</Badge>
                <Badge tone="info">missing</Badge>
              </div>
            </div>
            <p className="mt-1 text-sm text-ink-2">{doc.reason}</p>
          </div>
        ))}
        {uploaded.length ? (
          <p className="pt-1 text-xs text-ink-2">
            Present: {uploaded.map((doc) => doc.label).join(", ")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function DocumentsPanel({ run }: { run: DocumentVerificationRunResponse }) {
  return (
    <Card>
      <CardHeader>
        <SectionTitle>Uploaded documents</SectionTitle>
        <CardDescription>Detected types and extraction status.</CardDescription>
      </CardHeader>
      <CardContent>
        {!run.documents.length ? (
          <EmptyState
            title="No documents uploaded"
            description="Upload shipment documents to compare fields before customs filing or incentive claims."
          />
        ) : (
          <div className="grid gap-2 md:grid-cols-2">
            {run.documents.map((document) => (
              <div key={document.id} className="rounded-panel border border-line bg-surface p-3">
                <p className="truncate font-semibold text-ink">{document.file_name}</p>
                <p className="mt-1 text-xs text-ink-2">
                  {document.document_type || "not detected"} / {document.extraction_status}
                </p>
                {document.extraction_error ? (
                  <p className="mt-2 text-xs text-danger-fg">{document.extraction_error}</p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FieldsPanel({
  fieldsByDocument,
}: {
  fieldsByDocument: Array<{ document: string; fields: DocumentExtractedFieldResponse[] }>;
}) {
  return (
    <Card>
      <CardHeader>
        <SectionTitle>Extracted fields</SectionTitle>
        <CardDescription>
          Values are grouped by document and include evidence references.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!fieldsByDocument.length ? <EmptyState title="No extracted fields yet" /> : null}
        {fieldsByDocument.map((group) => (
          <div key={group.document}>
            <h3 className="mb-2 text-sm font-semibold text-ink">{group.document}</h3>
            <div className="overflow-x-auto rounded-panel border border-line">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-surface-2 text-xs font-medium text-ink-2">
                  <tr>
                    <th scope="col" className="px-3 py-2">
                      Field
                    </th>
                    <th scope="col" className="px-3 py-2">
                      Value
                    </th>
                    <th scope="col" className="px-3 py-2 text-right">
                      Confidence
                    </th>
                    <th scope="col" className="px-3 py-2 text-right">
                      Page
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {group.fields.map((field) => (
                    <tr key={field.id} className="border-t border-line">
                      <td className="px-3 py-2 font-medium">{field.field_label}</td>
                      <td className="px-3 py-2">
                        {field.raw_value || field.normalized_value || "-"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {Math.round(field.confidence_score)}%
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {field.page_number ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function IssuesPanel({
  issuesBySeverity,
  selectedIssue,
  busy,
  onSelect,
  onResolve,
  onIgnore,
}: {
  issuesBySeverity: Map<string, DocumentVerificationIssueResponse[]>;
  selectedIssue: DocumentVerificationIssueResponse | null;
  busy: boolean;
  onSelect: (issue: DocumentVerificationIssueResponse | null) => void;
  onResolve: (id: string) => void;
  onIgnore: (id: string) => void;
}) {
  const total = Array.from(issuesBySeverity.values()).flat().length;
  return (
    <Card>
      <CardHeader>
        <SectionTitle>Audit issues</SectionTitle>
        <CardDescription>
          {total
            ? "Critical mismatch found. Review before filing or claiming."
            : "No major mismatches found. Manual review is still recommended before filing."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {SEVERITY_ORDER.map((severity) => {
          const issues = issuesBySeverity.get(severity) ?? [];
          if (!issues.length) return null;
          return (
            <div key={severity}>
              <p className="mb-2 text-xs font-semibold capitalize text-ink-2">
                {severity} ({issues.length})
              </p>
              <div className="space-y-2">
                {issues.map((issue) => (
                  <div key={issue.id} className="rounded-panel border border-line bg-surface p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-ink">{issue.title}</p>
                        <p className="mt-1 text-sm text-ink-2">{issue.description}</p>
                        <p className="mt-1 text-xs capitalize text-ink-2">Status: {issue.status}</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" variant="secondary" onClick={() => onSelect(issue)}>
                          Evidence
                        </Button>
                        <Button size="sm" disabled={busy} onClick={() => onResolve(issue.id)}>
                          Resolve
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={busy}
                          onClick={() => onIgnore(issue.id)}
                        >
                          Ignore
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
        {selectedIssue ? (
          <div className="rounded-panel border border-brand bg-brand-soft p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-ink">Evidence: {selectedIssue.title}</p>
                <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-panel bg-surface p-3 text-xs text-ink">
                  {JSON.stringify(
                    selectedIssue.evidence_json ?? selectedIssue.actual_values_json,
                    null,
                    2
                  )}
                </pre>
              </div>
              <Button size="sm" variant="secondary" onClick={() => onSelect(null)}>
                Close
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function groupIssues(issues: DocumentVerificationIssueResponse[]) {
  const grouped = new Map<string, DocumentVerificationIssueResponse[]>();
  for (const severity of SEVERITY_ORDER) grouped.set(severity, []);
  for (const issue of issues) grouped.get(issue.severity)?.push(issue);
  return grouped;
}

function groupFields(run: DocumentVerificationRunResponse | undefined) {
  if (!run) return [];
  return run.documents
    .map((document) => ({
      document: `${document.file_name} (${document.document_type || "unknown"})`,
      fields: run.fields.filter((field) => field.document_id === document.id),
    }))
    .filter((group) => group.fields.length);
}

function ErrorBox({ error }: { error: unknown }) {
  return <Alert tone="danger" title={userMessageForError(error)} />;
}
