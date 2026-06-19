import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Button, Card, CardContent, CardHeader, CardTitle } from "@repo/ui";
import type { ShipmentResponse } from "@repo/shared";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

function RiskBadge({ stage }: { stage: string }) {
  const label = stage === "pre_shipment" ? "Pre-shipment" : "Post-shipment";
  const cls = stage === "pre_shipment"
    ? "bg-amber-500/15 text-amber-300 border-amber-500/20"
    : "bg-green-500/15 text-green-300 border-green-500/20";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>
  );
}

function ShipmentCard({ shipment, onDelete }: { shipment: ShipmentResponse; onDelete: (id: string) => void }) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-slate-900/60 p-5 transition-colors hover:border-cyan-500/30">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-100">{shipment.product_name}</p>
          <p className="mt-0.5 text-sm text-slate-400">HSN {shipment.hsn_code} · {shipment.destination_country}</p>
        </div>
        <RiskBadge stage={shipment.shipment_stage} />
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs text-slate-500">
        <span>{shipment.incoterm}</span>
        <span className="capitalize">{shipment.shipment_mode}</span>
        <span>{shipment.fob_value ? `${shipment.invoice_currency} ${shipment.fob_value.toLocaleString()}` : "—"}</span>
      </div>
      <div className="flex gap-2 pt-1">
        <Link to={`/shipments/${shipment.id}`} className="flex-1">
          <Button className="w-full" variant="secondary">Open</Button>
        </Link>
        <Button
          variant="secondary"
          onClick={() => onDelete(shipment.id)}
          className="text-rose-400 hover:text-rose-300"
        >
          Delete
        </Button>
      </div>
    </div>
  );
}

export function ShipmentsPage() {
  const { session, token, setSession } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const shipmentsQuery = useQuery({
    queryKey: ["shipments", token],
    queryFn: () => api.listShipments(token!),
    enabled: Boolean(token),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteShipment(id, token!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shipments"] }),
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
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Shipments</h2>
          <p className="mt-0.5 text-sm text-slate-400">Each shipment walks through checklist → documents → verification report.</p>
        </div>
        <Button onClick={() => navigate("/shipments/new")}>+ New Shipment</Button>
      </div>

      {shipmentsQuery.isLoading && (
        <p className="text-sm text-slate-400">Loading shipments…</p>
      )}

      {shipmentsQuery.isError && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
          {shipmentsQuery.error instanceof Error ? shipmentsQuery.error.message : "Failed to load shipments."}
        </div>
      )}

      {shipmentsQuery.data?.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-slate-400">No shipments yet.</p>
            <p className="mt-1 text-sm text-slate-500">Create your first shipment profile to get started.</p>
            <Button className="mt-4" onClick={() => navigate("/shipments/new")}>Create shipment</Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {shipmentsQuery.data?.map((s) => (
          <ShipmentCard key={s.id} shipment={s} onDelete={(id) => deleteMutation.mutate(id)} />
        ))}
      </div>
    </DashboardShell>
  );
}
