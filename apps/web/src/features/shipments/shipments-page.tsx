import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Button, Card, CardContent } from "@repo/ui";
import type { ShipmentResponse } from "@repo/shared";
import { useState } from "react";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { SkeletonCard } from "../../lib/ui";

function StageBadge({ stage }: { stage: string }) {
  const isPre = stage === "pre_shipment";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${
        isPre
          ? "border-cyan-300/20 bg-cyan-300/10 text-cyan-100"
          : "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
      }`}
    >
      {isPre ? "Pre-shipment" : "Post-shipment"}
    </span>
  );
}

function ShipmentCard({
  shipment,
  onDelete,
}: {
  shipment: ShipmentResponse;
  onDelete: (id: string) => void;
}) {
  function handleDelete() {
    if (window.confirm(`Delete "${shipment.product_name}"? This cannot be undone.`)) {
      onDelete(shipment.id);
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-white/10 bg-slate-900/75 p-5 shadow-xl shadow-slate-950/10 backdrop-blur transition-colors hover:border-cyan-300/25">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-semibold text-slate-100">{shipment.product_name}</p>
          <p className="mt-0.5 text-sm text-slate-500">
            HSN {shipment.hsn_code} / {shipment.destination_country}
          </p>
        </div>
        <StageBadge stage={shipment.shipment_stage} />
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Meta label="Mode" value={shipment.shipment_mode} />
        <Meta label="Terms" value={shipment.incoterm} />
        <Meta
          label="FOB"
          value={
            shipment.fob_value
              ? `${shipment.invoice_currency} ${shipment.fob_value.toLocaleString()}`
              : "-"
          }
        />
      </div>

      <div className="flex gap-2">
        <Link to={`/shipments/${shipment.id}`} className="flex-1">
          <Button className="w-full" variant="secondary" size="sm">
            Open
          </Button>
        </Link>
        <Button
          variant="danger"
          size="sm"
          onClick={handleDelete}
          aria-label={`Delete ${shipment.product_name}`}
        >
          Delete
        </Button>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-600">{label}</p>
      <p className="mt-0.5 text-xs capitalize text-slate-400">{value}</p>
    </div>
  );
}

export function ShipmentsPage() {
  const { session, token, setSession } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [importFile, setImportFile] = useState<File | null>(null);

  const shipmentsQuery = useQuery({
    queryKey: ["shipments", token],
    queryFn: () => api.listShipments(token!),
    enabled: Boolean(token),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteShipment(id, token!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shipments"] }),
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

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-slate-50">Shipments</h2>
          <p className="mt-0.5 text-sm text-slate-500">
            Each shipment walks through checklist, documents, and AI verification.
          </p>
        </div>
        <Button size="sm" onClick={() => navigate("/shipments/new")}>
          + New shipment
        </Button>
      </div>

      <Card className="mb-5">
        <CardContent className="flex flex-col gap-3 py-4 md:flex-row md:items-center">
          <div className="flex-1">
            <p className="text-sm font-medium text-slate-200">Bulk shipment import</p>
            <p className="text-xs text-slate-500">
              Upload CSV or XLSX using the shipment field names. Invalid rows are reported without
              blocking valid rows.
            </p>
          </div>
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={(event) => setImportFile(event.target.files?.[0] ?? null)}
            className="text-sm text-slate-400 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-xs file:text-slate-300"
          />
          <Button
            size="sm"
            variant="secondary"
            disabled={!importFile || importMutation.isPending}
            onClick={() => importMutation.mutate()}
          >
            {importMutation.isPending ? "Importing..." : "Import"}
          </Button>
          {importMutation.data ? (
            <p className="text-xs text-emerald-300">
              {importMutation.data.created} created, {importMutation.data.failed} failed
            </p>
          ) : null}
          {importMutation.isError ? (
            <p className="text-xs text-rose-300">
              {importMutation.error instanceof Error
                ? importMutation.error.message
                : "Import failed."}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {shipmentsQuery.isError && (
        <div
          className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/8 px-4 py-3 text-sm text-rose-300"
          role="alert"
        >
          <span aria-hidden="true">!</span>
          {shipmentsQuery.error instanceof Error
            ? shipmentsQuery.error.message
            : "Failed to load shipments."}
        </div>
      )}

      {shipmentsQuery.isLoading && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {!shipmentsQuery.isLoading && shipmentsQuery.data?.length === 0 && (
        <Card>
          <CardContent className="py-16 text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-200">
              Shipment workspace
            </p>
            <p className="mt-4 font-medium text-slate-300">No shipments yet</p>
            <p className="mt-1 text-sm text-slate-500">
              Create a shipment profile to generate a document checklist and run AI verification.
            </p>
            <Button className="mt-6" onClick={() => navigate("/shipments/new")}>
              Create first shipment
            </Button>
          </CardContent>
        </Card>
      )}

      {(shipmentsQuery.data?.length ?? 0) > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {shipmentsQuery.data!.map((s) => (
            <ShipmentCard key={s.id} shipment={s} onDelete={(id) => deleteMutation.mutate(id)} />
          ))}
        </div>
      )}
    </DashboardShell>
  );
}
