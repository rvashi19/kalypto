import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  ConfirmDialog,
  EmptyState,
  FileDropzone,
  PageHeader,
  QueryState,
  buttonClasses,
} from "@repo/ui";
import type { ShipmentResponse } from "@repo/shared";
import { useState } from "react";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const MAX_IMPORT_BYTES = 10 * 1024 * 1024;

function StageBadge({ stage }: { stage: string }) {
  return stage === "pre_shipment" ? (
    <Badge tone="info">Pre-shipment</Badge>
  ) : (
    <Badge tone="success">Post-shipment</Badge>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-3">{label}</dt>
      <dd className="mt-0.5 text-sm capitalize text-ink">{value}</dd>
    </div>
  );
}

function ShipmentCard({
  shipment,
  onRequestDelete,
}: {
  shipment: ShipmentResponse;
  onRequestDelete: (shipment: ShipmentResponse) => void;
}) {
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-semibold text-ink">{shipment.product_name}</p>
          <p className="mt-0.5 text-sm text-ink-2">
            HSN <span className="font-mono">{shipment.hsn_code}</span> / {shipment.destination_country}
          </p>
        </div>
        <StageBadge stage={shipment.shipment_stage} />
      </div>

      <dl className="grid grid-cols-3 gap-2">
        <Meta label="Mode" value={shipment.shipment_mode} />
        <Meta label="Terms" value={shipment.incoterm} />
        <Meta
          label="FOB"
          value={
            shipment.fob_value
              ? `${shipment.invoice_currency} ${shipment.fob_value.toLocaleString("en-IN")}`
              : "-"
          }
        />
      </dl>

      <div className="flex gap-2">
        <Link to={`/shipments/${shipment.id}`} className={buttonClasses("secondary", "sm", "flex-1")}>
          Open
        </Link>
        <Button
          variant="danger"
          size="sm"
          onClick={() => onRequestDelete(shipment)}
          aria-label={`Delete ${shipment.product_name}`}
        >
          Delete
        </Button>
      </div>
    </Card>
  );
}

export function ShipmentsPage() {
  const { session, token, setSession } = useAuth();
  const qc = useQueryClient();
  const [importFile, setImportFile] = useState<File | null>(null);
  const [pendingDelete, setPendingDelete] = useState<ShipmentResponse | null>(null);

  const shipmentsQuery = useQuery({
    queryKey: ["shipments", token],
    queryFn: () => api.listShipments(token!),
    enabled: Boolean(token),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteShipment(id, token!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shipments"] }),
    onSettled: () => setPendingDelete(null),
  });

  const importMutation = useMutation({
    mutationFn: () => api.importShipments(importFile!, token!),
    onSuccess: () => {
      setImportFile(null);
      qc.invalidateQueries({ queryKey: ["shipments"] });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => { if (token) await api.logout(token); },
    onSettled: () => setSession(null),
  });

  const shipments = shipmentsQuery.data ?? [];

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <PageHeader
        title="Shipments"
        breadcrumbs={[{ label: "Workspace" }, { label: "Shipments" }]}
        meta={<span>Each shipment walks through checklist, documents, and AI verification.</span>}
        actions={
          <Link to="/shipments/new" className={buttonClasses("primary", "md")}>
            New shipment
          </Link>
        }
      />

      <Card className="mb-5">
        <CardContent className="space-y-3 pt-4">
          <div>
            <h2 className="text-base font-semibold text-ink">Bulk shipment import</h2>
            <p className="text-sm text-ink-2">
              Upload CSV or XLSX using the shipment field names. Invalid rows are reported without
              blocking valid rows.
            </p>
          </div>
          <FileDropzone
            accept=".csv,.xlsx"
            maxBytes={MAX_IMPORT_BYTES}
            file={importFile}
            onFileChange={setImportFile}
            label="Choose a CSV or XLSX file or drop it here"
            disabled={importMutation.isPending}
          />
          <div>
            <Button
              size="sm"
              variant="secondary"
              disabled={!importFile}
              loading={importMutation.isPending}
              onClick={() => importMutation.mutate()}
            >
              {importMutation.isPending ? "Importing..." : "Import"}
            </Button>
          </div>
          {importMutation.data ? (
            <Alert tone="success" title="Import finished">
              {importMutation.data.created} created, {importMutation.data.failed} failed
            </Alert>
          ) : null}
          {importMutation.isError ? (
            <Alert tone="danger" title="Import failed">
              {userMessageForError(importMutation.error)}
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      {deleteMutation.isError && (
        <Alert tone="danger" title="Could not delete shipment" className="mb-4">
          {userMessageForError(deleteMutation.error)}
        </Alert>
      )}

      <QueryState
        isLoading={shipmentsQuery.isLoading}
        isError={shipmentsQuery.isError}
        error={userMessageForError(shipmentsQuery.error)}
        onRetry={() => void shipmentsQuery.refetch()}
        isEmpty={shipments.length === 0}
        empty={
          <EmptyState
            title="No shipments yet"
            description="Create a shipment profile to generate a document checklist and run AI verification."
            action={
              <Link to="/shipments/new" className={buttonClasses("primary", "md")}>
                Create first shipment
              </Link>
            }
          />
        }
      >
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {shipments.map((s) => (
            <ShipmentCard key={s.id} shipment={s} onRequestDelete={setPendingDelete} />
          ))}
        </div>
      </QueryState>

      <ConfirmDialog
        open={pendingDelete !== null}
        title={`Delete "${pendingDelete?.product_name ?? ""}"?`}
        description="This cannot be undone."
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => pendingDelete && deleteMutation.mutate(pendingDelete.id)}
        onCancel={() => setPendingDelete(null)}
      />
    </DashboardShell>
  );
}
