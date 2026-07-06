import type {
  DocumentExtractedFieldResponse,
  DocumentVerificationIssueResponse,
  DocumentVerificationRunCreate,
  DocumentVerificationRunResponse,
} from "@repo/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { inputCls } from "../../lib/ui";

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
  const { session, token, setSession } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<DocumentVerificationRunCreate>(EMPTY_FORM);
  const [files, setFiles] = useState<File[]>([]);
  const [selectedIssue, setSelectedIssue] = useState<DocumentVerificationIssueResponse | null>(null);

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
      action === "resolve" ? api.resolveVerifierIssue(id, token!) : api.ignoreVerifierIssue(id, token!),
    onSuccess: () => {
      setSelectedIssue(null);
      queryClient.invalidateQueries({ queryKey: ["document-verifier-run", runId] });
    },
  });

  const pdfMutation = useMutation({
    mutationFn: () => api.downloadVerifierReportPdf(runId!, token!),
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });

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
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-[#1868db]">
            Audit - AI Document Verifier
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#101214]">
            Compare shipment documents before filing or claiming
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#42526e]">
            This audit is based on uploaded documents and source-backed KALYPTO data. Verify with
            your CHA/customs broker before filing.
          </p>
        </div>
        {runId ? (
          <Link to="/document-verifier">
            <Button variant="secondary">New run</Button>
          </Link>
        ) : null}
      </div>

      {!runId ? (
        <div className="grid gap-5 lg:grid-cols-[420px_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>Create verification run</CardTitle>
              <CardDescription>
                Upload shipment documents to compare fields before customs filing or incentive
                claims.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Field label="Title" value={form.title} onChange={(title) => setForm({ ...form, title })} />
              <Field
                label="Reference number"
                value={form.reference_number ?? ""}
                onChange={(reference_number) => setForm({ ...form, reference_number })}
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <Field
                  label="Origin"
                  value={form.origin_country ?? ""}
                  onChange={(origin_country) => setForm({ ...form, origin_country })}
                />
                <Field
                  label="Destination"
                  value={form.destination_country ?? ""}
                  onChange={(destination_country) => setForm({ ...form, destination_country })}
                />
              </div>
              <Field
                label="HSN"
                value={form.hsn_code ?? ""}
                onChange={(hsn_code) => setForm({ ...form, hsn_code })}
              />
              <Field
                label="Product"
                value={form.product_description ?? ""}
                onChange={(product_description) => setForm({ ...form, product_description })}
              />
              <Button
                className="w-full"
                disabled={createRunMutation.isPending || !form.title.trim()}
                onClick={() => createRunMutation.mutate()}
              >
                {createRunMutation.isPending ? "Creating..." : "Create run"}
              </Button>
              {createRunMutation.error ? <ErrorBox error={createRunMutation.error} /> : null}
            </CardContent>
          </Card>
          <RunList runs={runs} loading={runsQuery.isLoading} />
        </div>
      ) : null}

      {runId ? (
        runQuery.isLoading ? (
          <Card>
            <CardContent className="p-6 text-sm text-[#42526e]">Loading verification run...</CardContent>
          </Card>
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
          <Card>
            <CardContent className="p-6 text-sm text-red-700">Verification run was not found.</CardContent>
          </Card>
        )
      ) : null}
    </DashboardShell>
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
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[#42526e]">
        {label}
      </span>
      <input className={inputCls} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function RunList({ runs, loading }: { runs: DocumentVerificationRunResponse[]; loading: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent verification runs</CardTitle>
        <CardDescription>Open a run to upload, extract, verify, and review issues.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {loading ? <p className="text-sm text-[#42526e]">Loading runs...</p> : null}
        {!loading && !runs.length ? (
          <p className="rounded border border-dashed border-[#dfe1e6] p-6 text-sm text-[#42526e]">
            No document verification runs yet.
          </p>
        ) : null}
        {runs.map((run) => (
          <Link
            key={run.id}
            to={`/document-verifier/${run.id}`}
            className="block rounded border border-[#dfe1e6] bg-white p-4 transition hover:border-[#1868db]"
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-[#101214]">{run.title}</p>
                <p className="mt-1 text-xs text-[#42526e]">
                  {run.reference_number || "No reference"} / {run.status}
                </p>
              </div>
              <span className="text-sm text-[#1868db]">{run.issues.length} issues</span>
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
        <CardTitle>{run.title}</CardTitle>
        <CardDescription>{run.reference_number || "No reference number"}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 text-sm">
        <Metric label="Status" value={run.status.replaceAll("_", " ")} />
        <Metric label="Documents" value={String(run.documents.length)} />
        <Metric label="Fields" value={String(run.fields.length)} />
        <Metric label="Open issues" value={String(run.issues.filter((i) => i.status === "open").length)} />
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[#dfe1e6] bg-[#f7f8f9] p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[#42526e]">
        {label}
      </p>
      <p className="mt-1 font-semibold capitalize text-[#101214]">{value}</p>
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
        <CardTitle>Upload documents</CardTitle>
        <CardDescription>Accepted: PDF, XLSX, CSV, JPG, JPEG, PNG.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <input
          multiple
          type="file"
          accept=".pdf,.xlsx,.csv,.jpg,.jpeg,.png"
          onChange={(event) => onFiles(Array.from(event.target.files ?? []))}
          className="w-full rounded border border-[#dfe1e6] bg-white p-2 text-sm"
        />
        {files.length ? (
          <p className="text-xs text-[#42526e]">{files.map((file) => file.name).join(", ")}</p>
        ) : (
          <p className="text-xs text-[#42526e]">No documents selected.</p>
        )}
        <Button className="w-full" disabled={!files.length || uploading} onClick={onUpload}>
          {uploading ? "Uploading..." : "Upload documents"}
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
  const readyToVerify = hasDocs && run.documents.every((doc) => doc.extraction_status === "extracted");
  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit actions</CardTitle>
        <CardDescription>Extract fields first, then run verification.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <Button className="w-full" disabled={!hasDocs || extracting} onClick={onExtract}>
          {extracting ? "Extracting..." : "Extract fields"}
        </Button>
        <Button className="w-full" disabled={!readyToVerify || verifying} onClick={onVerify}>
          {verifying ? "Verifying..." : "Run verification"}
        </Button>
        <Button className="w-full" variant="secondary" disabled={!run.report || downloading} onClick={onDownload}>
          {downloading ? "Preparing PDF..." : "Download report PDF"}
        </Button>
        {extractError ? <ErrorBox error={extractError} /> : null}
        {verifyError ? <ErrorBox error={verifyError} /> : null}
        {pdfError ? <ErrorBox error={pdfError} /> : null}
      </CardContent>
    </Card>
  );
}

function DocumentsPanel({ run }: { run: DocumentVerificationRunResponse }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Uploaded documents</CardTitle>
        <CardDescription>Detected types and extraction status.</CardDescription>
      </CardHeader>
      <CardContent>
        {!run.documents.length ? (
          <p className="rounded border border-dashed border-[#dfe1e6] p-6 text-sm text-[#42526e]">
            Upload shipment documents to compare fields before customs filing or incentive claims.
          </p>
        ) : (
          <div className="grid gap-2 md:grid-cols-2">
            {run.documents.map((document) => (
              <div key={document.id} className="rounded border border-[#dfe1e6] bg-white p-3">
                <p className="truncate font-semibold text-[#101214]">{document.file_name}</p>
                <p className="mt-1 text-xs text-[#42526e]">
                  {document.document_type || "not detected"} / {document.extraction_status}
                </p>
                {document.extraction_error ? (
                  <p className="mt-2 text-xs text-amber-700">{document.extraction_error}</p>
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
        <CardTitle>Extracted fields</CardTitle>
        <CardDescription>Values are grouped by document and include evidence references.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!fieldsByDocument.length ? (
          <p className="text-sm text-[#42526e]">No extracted fields yet.</p>
        ) : null}
        {fieldsByDocument.map((group) => (
          <div key={group.document}>
            <p className="mb-2 text-sm font-semibold text-[#101214]">{group.document}</p>
            <div className="overflow-x-auto rounded border border-[#dfe1e6]">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-[#f7f8f9] text-xs uppercase tracking-[0.12em] text-[#42526e]">
                  <tr>
                    <th className="px-3 py-2">Field</th>
                    <th className="px-3 py-2">Value</th>
                    <th className="px-3 py-2">Confidence</th>
                    <th className="px-3 py-2">Page</th>
                  </tr>
                </thead>
                <tbody>
                  {group.fields.map((field) => (
                    <tr key={field.id} className="border-t border-[#dfe1e6]">
                      <td className="px-3 py-2 font-medium">{field.field_label}</td>
                      <td className="px-3 py-2">{field.raw_value || field.normalized_value || "-"}</td>
                      <td className="px-3 py-2">{Math.round(field.confidence_score)}%</td>
                      <td className="px-3 py-2">{field.page_number ?? "-"}</td>
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
        <CardTitle>Audit issues</CardTitle>
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
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-[#42526e]">
                {severity} ({issues.length})
              </p>
              <div className="space-y-2">
                {issues.map((issue) => (
                  <div key={issue.id} className="rounded border border-[#dfe1e6] bg-white p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-[#101214]">{issue.title}</p>
                        <p className="mt-1 text-sm text-[#42526e]">{issue.description}</p>
                        <p className="mt-1 text-xs capitalize text-[#42526e]">Status: {issue.status}</p>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" variant="secondary" onClick={() => onSelect(issue)}>
                          Evidence
                        </Button>
                        <Button size="sm" disabled={busy} onClick={() => onResolve(issue.id)}>
                          Resolve
                        </Button>
                        <Button size="sm" variant="secondary" disabled={busy} onClick={() => onIgnore(issue.id)}>
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
          <div className="rounded border border-[#1868db] bg-[#e9f2fe] p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-[#101214]">Evidence: {selectedIssue.title}</p>
                <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-white p-3 text-xs text-[#172b4d]">
                  {JSON.stringify(selectedIssue.evidence_json ?? selectedIssue.actual_values_json, null, 2)}
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
  return (
    <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
      {userMessageForError(error)}
    </div>
  );
}
