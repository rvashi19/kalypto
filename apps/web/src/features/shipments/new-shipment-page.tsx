import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Input,
  PageHeader,
  Select,
  buttonClasses,
} from "@repo/ui";
import type { ShipmentCreate, ShipmentMode, ShipmentStage } from "@repo/shared";
import { DashboardShell } from "../../components/layout/dashboard-shell";
import { api, userMessageForError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useLogout } from "../../lib/use-logout";

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

function HsnRateCard({
  hsn,
  fobValue,
  token,
}: {
  hsn: string;
  fobValue: number | null | undefined;
  token: string;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["hsn-rates", hsn, fobValue],
    queryFn: () => api.getHsnRates(hsn, token, fobValue ?? undefined),
    enabled: hsn.length >= 4,
    staleTime: 60_000,
  });

  if (!hsn || hsn.length < 4) return null;
  if (isLoading) return <p className="text-xs text-ink-3">Looking up HSN rates...</p>;
  if (!data) return null;
  if (!data.found) return <p className="text-xs text-ink-3">{data.message}</p>;

  return (
    <div className="rounded-panel border border-info-border bg-info-bg px-4 py-3">
      <p className="text-sm font-semibold text-ink">{data.description}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {data.duty_drawback_rate != null && data.duty_drawback_rate > 0 && (
          <Badge tone="success">Duty Drawback {data.duty_drawback_rate}%</Badge>
        )}
        {data.rodtep_rate != null && data.rodtep_rate > 0 && (
          <Badge tone="info">RoDTEP {data.rodtep_rate}%</Badge>
        )}
        {data.rosctl_rate != null && data.rosctl_rate > 0 && (
          <Badge tone="neutral">RoSCTL {data.rosctl_rate}%</Badge>
        )}
      </div>
      {data.estimated_amounts_inr && (
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-ink-2">
          {Object.entries(data.estimated_amounts_inr).map(([scheme, amount]) => (
            <span key={scheme}>
              Est. {scheme.replace("_", " ")}:{" "}
              <span className="font-semibold text-ink">INR {amount.toLocaleString("en-IN")}</span>
            </span>
          ))}
        </div>
      )}
      {data.notes && <p className="mt-1.5 text-xs text-ink-2">{data.notes}</p>}
      {data.exchange_rate_note && <p className="mt-1 text-xs italic text-ink-3">{data.exchange_rate_note}</p>}
      <p className="mt-2 text-xs font-medium text-warning-fg">{data.disclaimer}</p>
    </div>
  );
}

export function NewShipmentPage() {
  const { session, token } = useAuth();
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

  const logoutMutation = useLogout();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (hasErrors) {
      setShowAllErrors(true);
      const form = e.currentTarget as HTMLFormElement;
      // Wait for the error render so aria-invalid is set before focusing.
      requestAnimationFrame(() =>
        form.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
      );
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
      <PageHeader
        title="New Shipment Profile"
        breadcrumbs={[{ label: "Shipments", href: "/shipments" }, { label: "New shipment" }]}
        renderLink={(crumb, className) => (
          <Link to={crumb.href!} className={className}>
            {crumb.label}
          </Link>
        )}
        meta={<span>Fill in the shipment details. We'll generate a document checklist and run AI verification.</span>}
      />

      <form onSubmit={handleSubmit} noValidate>
        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Product & Classification</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <Field label="Product name" required error={errorFor("product_name")}>
              <Input
                value={form.product_name}
                onChange={(e) => set("product_name", e.target.value)}
                onBlur={() => touch("product_name")}
                placeholder="e.g. Dried Red Chillies"
              />
            </Field>
            <div className="space-y-2">
              <Field label="HSN Code" required error={errorFor("hsn_code")}>
                <Input
                  className="font-mono"
                  value={form.hsn_code}
                  onChange={(e) => set("hsn_code", e.target.value)}
                  onBlur={() => touch("hsn_code")}
                  placeholder="e.g. 09042220"
                />
              </Field>
              {token ? <HsnRateCard hsn={form.hsn_code} fobValue={form.fob_value} token={token} /> : null}
            </div>
            <Field label="Exporter name" required error={errorFor("exporter_name")}>
              <Input
                value={form.exporter_name}
                onChange={(e) => set("exporter_name", e.target.value)}
                onBlur={() => touch("exporter_name")}
                placeholder="Your company name"
              />
            </Field>
            <Field label="Invoice currency" required>
              <Select
                value={form.invoice_currency}
                onChange={(e) => set("invoice_currency", e.target.value)}
              >
                {["USD", "EUR", "GBP", "AED", "SGD", "INR"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            </Field>
            <Field label="FOB value">
              <Input
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
            <Field label="Destination country" required error={errorFor("destination_country")}>
              <Input
                value={form.destination_country}
                onChange={(e) => set("destination_country", e.target.value)}
                onBlur={() => touch("destination_country")}
                placeholder="e.g. United States"
              />
            </Field>
            <Field label="Buyer country" required error={errorFor("buyer_country")}>
              <Input
                value={form.buyer_country}
                onChange={(e) => set("buyer_country", e.target.value)}
                onBlur={() => touch("buyer_country")}
                placeholder="e.g. United States"
              />
            </Field>
          </CardContent>
        </Card>

        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Shipment Terms</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <Field label="Incoterm" required>
              <Select
                value={form.incoterm}
                onChange={(e) => set("incoterm", e.target.value)}
              >
                {["EXW", "FOB", "CFR", "CIF", "DDP", "DAP", "FCA"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </Select>
            </Field>
            <Field label="Payment term" required error={errorFor("payment_term")}>
              <Input
                value={form.payment_term}
                onChange={(e) => set("payment_term", e.target.value)}
                onBlur={() => touch("payment_term")}
                placeholder="e.g. LC at sight, TT 30 days"
              />
            </Field>
            <Field label="Shipment mode" required>
              <Select
                value={form.shipment_mode}
                onChange={(e) => set("shipment_mode", e.target.value as ShipmentMode)}
              >
                <option value="sea">Sea</option>
                <option value="air">Air</option>
                <option value="courier">Courier</option>
              </Select>
            </Field>
            {form.shipment_mode === "sea" && (
              <Field label="Container type">
                <Input
                  value={form.container_type ?? ""}
                  onChange={(e) => set("container_type", e.target.value || null)}
                  placeholder="e.g. 20' FCL, LCL"
                />
              </Field>
            )}
            <Field label="Shipment stage" required>
              <Select
                value={form.shipment_stage}
                onChange={(e) => set("shipment_stage", e.target.value as ShipmentStage)}
              >
                <option value="pre_shipment">Pre-shipment</option>
                <option value="post_shipment">Post-shipment</option>
              </Select>
            </Field>
            <Field label="Port of loading">
              <Input
                value={form.port_of_loading ?? ""}
                onChange={(e) => set("port_of_loading", e.target.value || null)}
                placeholder="e.g. Nhava Sheva"
              />
            </Field>
            <Field label="Shipping bill no.">
              <Input
                value={form.shipping_bill_no ?? ""}
                onChange={(e) => set("shipping_bill_no", e.target.value || null)}
                placeholder="Optional"
              />
            </Field>
            <Field label="Shipment date">
              <Input
                type="date"
                value={form.shipment_date ?? ""}
                onChange={(e) => set("shipment_date", e.target.value || null)}
              />
            </Field>
          </CardContent>
        </Card>

        {mutation.isError && (
          <Alert tone="danger" title="Could not create shipment" className="mb-4">
            {userMessageForError(mutation.error)}
          </Alert>
        )}

        <div className="flex justify-end gap-3">
          <Link to="/shipments" className={buttonClasses("secondary", "md")}>
            Cancel
          </Link>
          <Button type="submit" loading={mutation.isPending}>
            {mutation.isPending ? "Creating..." : "Create and get checklist"}
          </Button>
        </div>
      </form>
    </DashboardShell>
  );
}
