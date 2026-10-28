import {
  Alert,
  Button,
  Card,
  CardContent,
  CardHeader,
  EmptyState,
  FileDropzone,
  QueryState,
  Spinner,
} from "@repo/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ChangeEvent } from "react";

import { api } from "../../lib/api";

const EXTRACT_ACCEPT = ".pdf,.docx,.doc,.xlsx,.xls,.csv";
const EXTRACT_MAX_BYTES = 20 * 1024 * 1024;

export type ExtractResult = {
  extracted: Record<string, unknown>;
  confidence: number;
  missing_fields: string[];
  notes: string | null;
  used_llm: boolean;
};

export function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-base font-semibold text-ink">{title}</h2>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function ExtractPanel({
  token,
  onExtracted,
}: {
  token: string;
  onExtracted: (result: ExtractResult) => void;
}) {
  const [file, setFile] = useState<File | null>(null);

  const mut = useMutation({
    mutationFn: (f: File) => api.extractFromDocument(f, token),
    onSuccess: (res) => onExtracted(res),
  });

  return (
    <SectionCard title="Auto-fill from existing document">
      <p className="mb-3 text-sm text-ink-2">
        Upload a previous invoice, Excel sheet, or Word document and we will extract the information
        and fill in the form. Missing fields will be highlighted.
      </p>
      <FileDropzone
        accept={EXTRACT_ACCEPT}
        maxBytes={EXTRACT_MAX_BYTES}
        file={file}
        disabled={mut.isPending}
        label="Drop a PDF, Word, Excel or CSV file here (up to 20 MB)"
        onFileChange={(f) => {
          setFile(f);
          if (f) mut.mutate(f);
        }}
      />
      {mut.isPending && (
        <p role="status" className="mt-2 flex items-center gap-2 text-sm text-ink-2">
          <Spinner className="h-4 w-4" /> Extracting information…
        </p>
      )}
      {mut.error && (
        <Alert tone="danger" title="Could not extract this document" className="mt-3">
          {(mut.error as Error).message}
        </Alert>
      )}
    </SectionCard>
  );
}

export function LogoPanel({ token }: { token: string }) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const { data: hasLogo, refetch } = useQuery({
    queryKey: ["org-logo"],
    queryFn: async () => {
      const resp = await fetch(api.getLogoUrl(), {
        credentials: "include",
      });
      return resp.ok;
    },
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => api.uploadLogo(file, token),
    onSuccess: () => {
      refetch();
      setPreviewUrl(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => api.deleteLogo(token),
    onSuccess: () => {
      refetch();
      setPreviewUrl(null);
    },
  });

  function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    uploadMut.mutate(file);
  }

  return (
    <SectionCard title="Company logo">
      <p className="mb-3 text-sm text-ink-2">
        Upload once and your logo appears on all generated documents. PNG or JPG, under 2 MB.
      </p>

      {(hasLogo || previewUrl) && (
        <div className="mb-3 flex items-center gap-3">
          <img
            src={previewUrl ?? `${api.getLogoUrl()}?t=${Date.now()}`}
            alt="Company logo"
            className="h-12 max-w-32 rounded-control border border-line-strong bg-surface object-contain p-1"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
          <Button
            size="sm"
            variant="ghost"
            loading={deleteMut.isPending}
            onClick={() => {
              if (confirm("Remove logo?")) deleteMut.mutate();
            }}
          >
            Remove
          </Button>
        </div>
      )}

      <label className="flex cursor-pointer items-center gap-2 rounded-panel border border-dashed border-line-strong bg-surface-2 px-3 py-2.5 text-sm text-ink-2 transition-colors focus-within:ring-2 focus-within:ring-brand hover:border-brand hover:text-ink">
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/svg+xml"
          className="sr-only"
          onChange={handleFile}
          disabled={uploadMut.isPending}
        />
        {uploadMut.isPending ? "Uploading…" : hasLogo ? "Replace logo" : "Upload logo"}
      </label>

      {uploadMut.error && (
        <Alert tone="danger" title="Could not upload the logo" className="mt-3">
          {(uploadMut.error as Error).message}
        </Alert>
      )}
      {deleteMut.error && (
        <Alert tone="danger" title="Could not remove the logo" className="mt-3">
          {(deleteMut.error as Error).message}
        </Alert>
      )}
    </SectionCard>
  );
}

export function PacksHistory({ token }: { token: string }) {
  const qc = useQueryClient();
  const packsQuery = useQuery({
    queryKey: ["document-packs"],
    queryFn: () => api.listDocumentPacks(token),
  });
  const packs = packsQuery.data ?? [];

  const downloadMut = useMutation({
    mutationFn: (packId: string) => api.downloadDocumentPack(packId, token),
  });

  const archiveMut = useMutation({
    mutationFn: (packId: string) => api.archiveDocumentPack(packId, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["document-packs"] }),
  });

  return (
    <QueryState
      isLoading={packsQuery.isLoading}
      isError={packsQuery.isError}
      error={packsQuery.error}
      onRetry={() => packsQuery.refetch()}
      isEmpty={!packs.length}
      empty={<EmptyState title="No saved document packs yet" />}
    >
      <div className="space-y-2">
        {(downloadMut.error || archiveMut.error) && (
          <Alert tone="danger" title="Could not complete that action">
            {((downloadMut.error ?? archiveMut.error) as Error).message}
          </Alert>
        )}
        {packs.map((pack) => (
          <div
            key={pack.id}
            className="flex items-center justify-between gap-4 rounded-card border border-line bg-surface px-4 py-3"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink">
                <span className="font-mono">{pack.pack_number ?? pack.id.slice(0, 8)}</span>
                {pack.invoice_number && (
                  <span className="ml-2 text-ink-2">
                    · <span className="font-mono">{pack.invoice_number}</span>
                  </span>
                )}
              </p>
              <p className="mt-0.5 truncate text-xs text-ink-2">
                {pack.buyer_name ?? "—"} · {pack.destination_country ?? "—"} · {pack.currency} ·{" "}
                {pack.status}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button
                size="sm"
                variant="secondary"
                loading={downloadMut.isPending && downloadMut.variables === pack.id}
                onClick={() => downloadMut.mutate(pack.id)}
              >
                Download
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  if (confirm("Archive this pack?")) archiveMut.mutate(pack.id);
                }}
              >
                Archive
              </Button>
            </div>
          </div>
        ))}
      </div>
    </QueryState>
  );
}
