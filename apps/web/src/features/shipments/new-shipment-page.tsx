import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button, Card, CardContent, CardHeader, CardTitle } from "@repo/ui";
import type { ShipmentCreate, ShipmentMode, ShipmentStage } from "@repo/shared";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { inputCls, selectCls, FieldError } from "../../lib/ui";

type RequiredField =
  | "product_name"
  | "hsn_code"
  | "exporter_name"
  | "destination_country"
  | "buyer_country"
  | "payment_term";

function getErrors(form: ShipmentCreate): Partial<Record<RequiredField, string>> {
  const e: Partial<Record<RequiredField, string>> = {};
  if (!form.product_name.trim()) e.product_name = "Product name is required.";
  if (!form.hsn_code.trim()) e.hsn_code = "HSN code is required.";
  if (!form.exporter_name.trim()) e.exporter_name = "Exporter name is required.";
  if (!form.destination_country.trim()) e.destination_country = "Destination country is required.";
  if (!form.buyer_country.trim()) e.buyer_country = "Buyer country is required.";
  if (!form.payment_term.trim()) e.payment_term = "Payment term is required.";
  return e;
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium uppercase tracking-wider text-slate-400">
        {label}
        {required && <span className="ml-1 text-rose-400">*</span>}
      </label>
      {children}
    </div>
  );
}

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
  if (!data.found) return <p className="mt-1.5 text-xs text-slate-500">{data.message}</p>;

  return (
    <div className="mt-2 rounded-lg border border-sky-500/20 bg-sky-500/8 px-4 py-3">
      <p className="text-xs font-semibold text-sky-300">{data.description}</p>
      <div className="mt-2 flex flex-wrap gap-2 text-xs">
        {data.duty_drawback_rate != null && data.duty_drawback_rate > 0 && (
          <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-emerald-300">
            Duty Drawback {data.duty_drawback_rate}%
          </span>
        )}
        {data.rodtep_rate != null && data.rodtep_rate > 0 && (
          <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2.5 py-0.5 text-indigo-300">
            RoDTEP {data.rodtep_rate}%
          </span>
        )}
        {data.rosctl_rate != null && data.rosctl_rate > 0 && (
          <span className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2.5 py-0.5 text-violet-300">
            RoSCTL {data.rosctl_rate}%
          </span>
        )}
      </div>
      {data.estimated_amounts_inr && (
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-300">
          {Object.entries(data.estimated_amounts_inr).map(([scheme, amount]) => (
            <span key={scheme}>
              Est. {scheme.replace("_", " ")}:{" "}
              <span className="font-semibold text-emerald-400">
                ₹{amount.toLocaleString("en-IN")}
              </span>
            </span>
          ))}
        </div>
      )}
      {data.notes && <p className="mt-1.5 text-xs text-slate-500">{data.notes}</p>}
      {data.exchange_rate_note && (
        <p className="mt-1 text-xs italic text-slate-600">{data.exchange_rate_note}</p>
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

  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [showAllErrors, setShowAllErrors] = useState(false);

  const errors = getErrors(form);
  const hasErrors = Object.values(errors).some(Boolean);

  function touch(field: string) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  function errorFor(field: RequiredField): string | undefined {
    return touched[field] || showAllErrors ? errors[field] : undefined;
  }

  const set = (key: keyof ShipmentCreate, value: unknown) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const mutation = useMutation({
    mutationFn: () => api.createShipment(form, token!),
    onSuccess: (data) => navigate(`/shipments/${data.id}`),
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (token) await api.logout(token);
    },
    onSettled: () => setSession(null),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (hasErrors) {
      setShowAllErrors(true);
      return;
    }
    mutation.mutate();
  }

  return (
    <DashboardShell
      organizationName={session?.organization.name ?? "Workspace"}
      role={session?.membership.role ?? "owner"}
      onLogout={() => logoutMutation.mutate()}
    >
      <div className="mb-5">
        <button
          onClick={() => navigate("/shipments")}
          className="text-sm text-slate-500 hover:text-slate-300"
        >
          ← Back to shipments
        </button>
        <h2 className="mt-2 text-xl font-semibold text-slate-50">New Shipment Profile</h2>
        <p className="mt-0.5 text-sm text-slate-400">
          Fill in the shipment details. We'll generate a document checklist and run AI
          verification.
        </p>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Product & Classification</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <Field label="Product name" required>
              <input
                className={inputCls}
                value={form.product_name}
                onChange={(e) => set("product_name", e.target.value)}
                onBlur={() => touch("product_name")}
                placeholder="e.g. Dried Red Chillies"
              />
              <FieldError message={errorFor("product_name")} />
            </Field>
            <Field label="HSN Code" required>
              <input
                className={inputCls}
                value={form.hsn_code}
                onChange={(e) => set("hsn_code", e.target.value)}
                onBlur={() => touch("hsn_code")}
                placeholder="e.g. 09042220"
              />
              <FieldError message={errorFor("hsn_code")} />
              <HsnRateCard hsn={form.hsn_code} fobValue={form.fob_value} />
            </Field>
            <Field label="Exporter name" required>
              <input
                className={inputCls}
                value={form.exporter_name}
                onChange={(e) => set("exporter_name", e.target.value)}
                onBlur={() => touch("exporter_name")}
                placeholder="Your company name"
              />
              <FieldError message={errorFor("exporter_name")} />
            </Field>
            <Field label="Invoice currency" required>
              <select
                className={selectCls}
                value={form.invoice_currency}
                onChange={(e) => set("invoice_currency", e.target.value)}
              >
                {["USD", "EUR", "GBP", "AED", "SGD", "INR"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="FOB value">
              <input
                className={inputCls}
                type="number"
                value={form.fob_value ?? ""}
                onChange={(e) =>
                  set("fob_value", e.target.value ? Number(e.target.value) : null)
                }
                placeholder="e.g. 25000"
              />
            </Field>
          </CardContent>
        </Card>

        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Destination & Buyer</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <Field label="Destination country" required>
              <input
                className={inputCls}
                value={form.destination_country}
                onChange={(e) => set("destination_country", e.target.value)}
                onBlur={() => touch("destination_country")}
                placeholder="e.g. United States"
              />
              <FieldError message={errorFor("destination_country")} />
            </Field>
            <Field label="Buyer country" required>
              <input
                className={inputCls}
                value={form.buyer_country}
                onChange={(e) => set("buyer_country", e.target.value)}
                onBlur={() => touch("buyer_country")}
                placeholder="e.g. United States"
              />
              <FieldError message={errorFor("buyer_country")} />
            </Field>
          </CardContent>
        </Card>

        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Shipment Terms</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <Field label="Incoterm" required>
              <select
                className={selectCls}
                value={form.incoterm}
                onChange={(e) => set("incoterm", e.target.value)}
              >
                {["EXW", "FOB", "CFR", "CIF", "DDP", "DAP", "FCA"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </Field>
            <Field label="Payment term" required>
              <input
                className={inputCls}
                value={form.payment_term}
                onChange={(e) => set("payment_term", e.target.value)}
                onBlur={() => touch("payment_term")}
                placeholder="e.g. LC at sight, TT 30 days"
              />
              <FieldError message={errorFor("payment_term")} />
            </Field>
            <Field label="Shipment mode" required>
              <select
                className={selectCls}
                value={form.shipment_mode}
                onChange={(e) => set("shipment_mode", e.target.value as ShipmentMode)}
              >
                <option value="sea">Sea</option>
                <option value="air">Air</option>
                <option value="courier">Courier</option>
              </select>
            </Field>
            {form.shipment_mode === "sea" && (
              <Field label="Container type">
                <input
                  className={inputCls}
                  value={form.container_type ?? ""}
                  onChange={(e) => set("container_type", e.target.value || null)}
                  placeholder="e.g. 20' FCL, LCL"
                />
              </Field>
            )}
            <Field label="Shipment stage" required>
              <select
                className={selectCls}
                value={form.shipment_stage}
                onChange={(e) => set("shipment_stage", e.target.value as ShipmentStage)}
              >
                <option value="pre_shipment">Pre-shipment</option>
                <option value="post_shipment">Post-shipment</option>
              </select>
            </Field>
            <Field label="Port of loading">
              <input
                className={inputCls}
                value={form.port_of_loading ?? ""}
                onChange={(e) => set("port_of_loading", e.target.value || null)}
                placeholder="e.g. Nhava Sheva"
              />
            </Field>
            <Field label="Shipping bill no.">
              <input
                className={inputCls}
                value={form.shipping_bill_no ?? ""}
                onChange={(e) => set("shipping_bill_no", e.target.value || null)}
                placeholder="Optional"
              />
            </Field>
            <Field label="Shipment date">
              <input
                className={inputCls}
                type="date"
                value={form.shipment_date ?? ""}
                onChange={(e) => set("shipment_date", e.target.value || null)}
              />
            </Field>
          </CardContent>
        </Card>

        {mutation.isError && (
          <div
            className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/8 px-4 py-3 text-sm text-rose-300"
            role="alert"
          >
            <span aria-hidden="true">✕</span>
            {mutation.error instanceof Error ? mutation.error.message : "Something went wrong."}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={() => navigate("/shipments")}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create & get checklist →"}
          </Button>
        </div>
      </form>
    </DashboardShell>
  );
}
