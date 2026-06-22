import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button, Card, CardContent, CardHeader, CardTitle, CardDescription } from "@repo/ui";
import type { ShipmentCreate, ShipmentMode, ShipmentStage } from "@repo/shared";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium uppercase tracking-wider text-slate-400">
        {label}{required && <span className="ml-1 text-rose-400">*</span>}
      </label>
      {children}
    </div>
  );
}

const inputCls = "rounded-xl border border-white/10 bg-slate-950/80 px-4 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400/40 placeholder:text-slate-600";
const selectCls = `${inputCls} cursor-pointer`;

function HsnRateCard({ hsn, fobValue }: { hsn: string; fobValue: number | null | undefined }) {
  const { data, isLoading } = useQuery({
    queryKey: ["hsn-rates", hsn, fobValue],
    queryFn: () => api.getHsnRates(hsn, fobValue ?? undefined),
    enabled: hsn.length >= 4,
    staleTime: 60_000,
  });

  if (!hsn || hsn.length < 4) return null;
  if (isLoading) return <p className="mt-1.5 text-xs text-slate-500">Looking up HSN rates…</p>;
  if (!data) return null;

  if (!data.found) {
    return (
      <p className="mt-1.5 text-xs text-slate-500">{data.message}</p>
    );
  }

  return (
    <div className="mt-2 rounded-xl border border-cyan-500/20 bg-cyan-500/5 px-4 py-3">
      <p className="text-xs font-semibold text-cyan-300">{data.description}</p>
      <div className="mt-2 flex flex-wrap gap-3 text-xs">
        {data.duty_drawback_rate != null && data.duty_drawback_rate > 0 && (
          <span className="rounded-full bg-green-500/15 px-2.5 py-0.5 text-green-300">
            Duty Drawback {data.duty_drawback_rate}%
          </span>
        )}
        {data.rodtep_rate != null && data.rodtep_rate > 0 && (
          <span className="rounded-full bg-blue-500/15 px-2.5 py-0.5 text-blue-300">
            RoDTEP {data.rodtep_rate}%
          </span>
        )}
        {data.rosctl_rate != null && data.rosctl_rate > 0 && (
          <span className="rounded-full bg-violet-500/15 px-2.5 py-0.5 text-violet-300">
            RoSCTL {data.rosctl_rate}%
          </span>
        )}
      </div>
      {data.estimated_amounts_inr && (
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-300">
          {Object.entries(data.estimated_amounts_inr).map(([scheme, amount]) => (
            <span key={scheme}>
              Est. {scheme.replace("_", " ")}:{" "}
              <span className="font-semibold text-green-400">₹{amount.toLocaleString("en-IN")}</span>
            </span>
          ))}
        </div>
      )}
      {data.notes && <p className="mt-1.5 text-xs text-slate-500">{data.notes}</p>}
      {data.exchange_rate_note && (
        <p className="mt-1 text-xs text-slate-600 italic">{data.exchange_rate_note}</p>
      )}
    </div>
  );
}

export function NewShipmentPage() {
  const { session, token, setSession } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState<ShipmentCreate>({
    exporter_name: session?.organization.name ?? "",
    product_name: "",
    hsn_code: "",
    destination_country: "",
    buyer_country: "",
    incoterm: "FOB",
    payment_term: "",
    shipment_mode: "sea",
    container_type: null,
    shipment_stage: "pre_shipment",
    fob_value: null,
    invoice_currency: "USD",
    shipping_bill_no: null,
    port_of_loading: null,
    shipment_date: null,
  });

  const set = (key: keyof ShipmentCreate, value: unknown) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const mutation = useMutation({
    mutationFn: () => api.createShipment(form, token!),
    onSuccess: (data) => navigate(`/shipments/${data.id}`),
  });

  const logoutMutation = useMutation({
    mutationFn: async () => { if (token) await api.logout(token); },
    onSettled: () => setSession(null),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <div className="mb-5">
        <button onClick={() => navigate("/shipments")} className="text-sm text-slate-500 hover:text-slate-300">
          ← Back to shipments
        </button>
        <h2 className="mt-2 text-xl font-semibold">New Shipment Profile</h2>
        <p className="mt-0.5 text-sm text-slate-400">Fill in the shipment details. We'll generate a document checklist and verify your docs against this profile.</p>
      </div>

      <form onSubmit={handleSubmit}>
        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Product & Classification</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <Field label="Product name" required>
              <input className={inputCls} value={form.product_name} onChange={(e) => set("product_name", e.target.value)} placeholder="e.g. Dried Red Chillies" required />
            </Field>
            <Field label="HSN Code" required>
              <input
                className={inputCls}
                value={form.hsn_code}
                onChange={(e) => set("hsn_code", e.target.value)}
                placeholder="e.g. 09042220"
                required
              />
              <HsnRateCard hsn={form.hsn_code} fobValue={form.fob_value} />
            </Field>
            <Field label="Exporter name" required>
              <input className={inputCls} value={form.exporter_name} onChange={(e) => set("exporter_name", e.target.value)} placeholder="Your company name" required />
            </Field>
            <Field label="Invoice currency" required>
              <select className={selectCls} value={form.invoice_currency} onChange={(e) => set("invoice_currency", e.target.value)}>
                {["USD", "EUR", "GBP", "AED", "SGD", "INR"].map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="FOB value">
              <input className={inputCls} type="number" value={form.fob_value ?? ""} onChange={(e) => set("fob_value", e.target.value ? Number(e.target.value) : null)} placeholder="e.g. 25000" />
            </Field>
          </CardContent>
        </Card>

        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Destination & Buyer</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <Field label="Destination country" required>
              <input className={inputCls} value={form.destination_country} onChange={(e) => set("destination_country", e.target.value)} placeholder="e.g. United States" required />
            </Field>
            <Field label="Buyer country" required>
              <input className={inputCls} value={form.buyer_country} onChange={(e) => set("buyer_country", e.target.value)} placeholder="e.g. United States" required />
            </Field>
          </CardContent>
        </Card>

        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Shipment Terms</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <Field label="Incoterm" required>
              <select className={selectCls} value={form.incoterm} onChange={(e) => set("incoterm", e.target.value)}>
                {["EXW", "FOB", "CFR", "CIF", "DDP", "DAP", "FCA"].map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Payment term" required>
              <input className={inputCls} value={form.payment_term} onChange={(e) => set("payment_term", e.target.value)} placeholder="e.g. LC at sight, TT 30 days" required />
            </Field>
            <Field label="Shipment mode" required>
              <select className={selectCls} value={form.shipment_mode} onChange={(e) => set("shipment_mode", e.target.value as ShipmentMode)}>
                <option value="sea">Sea</option>
                <option value="air">Air</option>
                <option value="courier">Courier</option>
              </select>
            </Field>
            {form.shipment_mode === "sea" && (
              <Field label="Container type">
                <input className={inputCls} value={form.container_type ?? ""} onChange={(e) => set("container_type", e.target.value || null)} placeholder="e.g. 20' FCL, LCL" />
              </Field>
            )}
            <Field label="Shipment stage" required>
              <select className={selectCls} value={form.shipment_stage} onChange={(e) => set("shipment_stage", e.target.value as ShipmentStage)}>
                <option value="pre_shipment">Pre-shipment</option>
                <option value="post_shipment">Post-shipment</option>
              </select>
            </Field>
            <Field label="Port of loading">
              <input className={inputCls} value={form.port_of_loading ?? ""} onChange={(e) => set("port_of_loading", e.target.value || null)} placeholder="e.g. Nhava Sheva" />
            </Field>
            <Field label="Shipping bill no.">
              <input className={inputCls} value={form.shipping_bill_no ?? ""} onChange={(e) => set("shipping_bill_no", e.target.value || null)} placeholder="Optional" />
            </Field>
            <Field label="Shipment date">
              <input className={inputCls} type="date" value={form.shipment_date ?? ""} onChange={(e) => set("shipment_date", e.target.value || null)} />
            </Field>
          </CardContent>
        </Card>

        {mutation.isError && (
          <div className="mb-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
            {mutation.error instanceof Error ? mutation.error.message : "Something went wrong."}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={() => navigate("/shipments")}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create & get checklist →"}
          </Button>
        </div>
      </form>
    </DashboardShell>
  );
}
