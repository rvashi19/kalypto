import { Button } from "@repo/ui";

import {
  CURRENCIES,
  EMPTY_ITEM,
  INCOTERMS,
  MODES,
  type FormState,
  type ItemRow,
} from "./document-builder-data";
import { FormField, SelectField } from "./document-builder-fields";
import { SectionCard } from "./document-builder-panels";

export function FormSections({
  form,
  set,
  missingFields,
  items,
  setItems,
  setItem,
  autoTotal,
}: {
  form: FormState;
  set: (k: keyof FormState) => (v: string) => void;
  missingFields: Set<string>;
  items: ItemRow[];
  setItems: React.Dispatch<React.SetStateAction<ItemRow[]>>;
  setItem: (idx: number, k: keyof ItemRow, v: string) => void;
  autoTotal: (idx: number, field: "quantity" | "unit_price" | "total_value", value: string) => void;
}) {
  return (
    <>
      <SectionCard title="Exporter / Shipper">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <FormField
              label="Company Name"
              value={form.company_name}
              onChange={set("company_name")}
              placeholder="Spice Exports Pvt Ltd"
              required
              highlight={missingFields.has("company_name")}
            />
          </div>
          <div className="sm:col-span-2">
            <FormField
              label="Address"
              value={form.address}
              onChange={set("address")}
              placeholder="12 Industrial Estate, Unjha"
              required
              highlight={missingFields.has("address")}
            />
          </div>
          <FormField label="City" value={form.city} onChange={set("city")} placeholder="Unjha" />
          <FormField
            label="State"
            value={form.state}
            onChange={set("state")}
            placeholder="Gujarat"
          />
          <FormField
            label="Postal Code"
            value={form.postal_code}
            onChange={set("postal_code")}
            placeholder="384170"
          />
          <FormField
            label="Country"
            value={form.country}
            onChange={set("country")}
            placeholder="India"
          />
          <FormField
            label="IEC"
            mono
            value={form.iec}
            onChange={set("iec")}
            placeholder="0900000001"
            highlight={missingFields.has("iec")}
          />
          <FormField
            label="GSTIN"
            mono
            value={form.gstin}
            onChange={set("gstin")}
            placeholder="24AAACP0000A1Z5"
            highlight={missingFields.has("gstin")}
          />
          <FormField
            label="Bank Name"
            value={form.bank_name}
            onChange={set("bank_name")}
            placeholder="State Bank of India"
            highlight={missingFields.has("bank_name")}
          />
          <FormField
            label="Account No."
            mono
            value={form.bank_account}
            onChange={set("bank_account")}
            placeholder="30000000001"
            highlight={missingFields.has("bank_account")}
          />
          <FormField
            label="IFSC / SWIFT"
            mono
            value={form.ifsc_swift}
            onChange={set("ifsc_swift")}
            placeholder="SBININBB210"
          />
          <FormField
            label="AD Code"
            mono
            value={form.ad_code}
            onChange={set("ad_code")}
            placeholder="1234567"
          />
        </div>
      </SectionCard>

      {/* Buyer */}
      <SectionCard title="Buyer / Consignee">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <FormField
              label="Buyer Name"
              value={form.buyer_name}
              onChange={set("buyer_name")}
              placeholder="Dubai Spices Trading LLC"
              required
              highlight={missingFields.has("buyer_name")}
            />
          </div>
          <div className="sm:col-span-2">
            <FormField
              label="Buyer Address"
              value={form.buyer_address}
              onChange={set("buyer_address")}
              placeholder="PO Box 12345, Jebel Ali Free Zone, Dubai"
            />
          </div>
          <FormField
            label="Buyer Country"
            value={form.buyer_country}
            onChange={set("buyer_country")}
            placeholder="UAE"
            required
            highlight={missingFields.has("buyer_country")}
          />
          <FormField
            label="Consignee Name (if different)"
            value={form.consignee_name}
            onChange={set("consignee_name")}
            placeholder="Same as buyer"
          />
          <div className="sm:col-span-2">
            <FormField
              label="Consignee Address"
              value={form.consignee_address}
              onChange={set("consignee_address")}
              placeholder="If different from buyer"
            />
          </div>
        </div>
      </SectionCard>

      {/* Shipment */}
      <SectionCard title="Shipment Details">
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            label="Invoice Number"
            mono
            value={form.invoice_number}
            onChange={set("invoice_number")}
            placeholder="SEP/2024-25/001"
            required
            highlight={missingFields.has("invoice_number")}
          />
          <FormField
            label="Invoice Date"
            value={form.invoice_date}
            onChange={set("invoice_date")}
            type="date"
            required
          />
          <FormField
            label="Buyer PO / Order No."
            value={form.buyer_order_number}
            onChange={set("buyer_order_number")}
            placeholder="PO-2024-001"
          />
          <FormField
            label="Country of Origin"
            value={form.country_of_origin}
            onChange={set("country_of_origin")}
            placeholder="India"
          />
          <FormField
            label="Country of Final Destination"
            value={form.country_of_final_destination}
            onChange={set("country_of_final_destination")}
            placeholder="UAE"
            required
          />
          <FormField
            label="Port of Loading"
            value={form.port_of_loading}
            onChange={set("port_of_loading")}
            placeholder="Mundra"
            highlight={missingFields.has("port_of_loading")}
          />
          <FormField
            label="Port of Discharge"
            value={form.port_of_discharge}
            onChange={set("port_of_discharge")}
            placeholder="Jebel Ali"
            highlight={missingFields.has("port_of_discharge")}
          />
          <SelectField
            label="Incoterm"
            value={form.incoterm}
            onChange={set("incoterm")}
            options={INCOTERMS}
            highlight={missingFields.has("incoterm")}
          />
          <SelectField
            label="Mode of Transport"
            value={form.mode_of_transport}
            onChange={set("mode_of_transport")}
            options={MODES}
          />
          <SelectField
            label="Currency"
            value={form.currency}
            onChange={set("currency")}
            options={CURRENCIES}
            highlight={missingFields.has("currency")}
          />
          <div className="sm:col-span-2">
            <FormField
              label="Payment Terms"
              value={form.payment_terms}
              onChange={set("payment_terms")}
              placeholder="30 days from BL date"
              highlight={missingFields.has("payment_terms")}
            />
          </div>
          <div className="sm:col-span-2">
            <FormField
              label="Marks & Numbers"
              value={form.marks_and_numbers}
              onChange={set("marks_and_numbers")}
              placeholder="SPICE / JEBEL ALI / 2025 / 001-020"
            />
          </div>
        </div>
      </SectionCard>

      {/* Line items */}
      <SectionCard title="Line Items">
        <div className="mb-4 flex justify-end">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setItems((rows) => [...rows, { ...EMPTY_ITEM }])}
          >
            + Add item
          </Button>
        </div>
        <div className="space-y-4">
          {items.map((row, idx) => (
            <div key={idx} className="rounded-panel border border-line bg-surface-2 p-3">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-ink">Item {idx + 1}</h3>
                {items.length > 1 && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setItems((rows) => rows.filter((_, i) => i !== idx))}
                  >
                    Remove
                  </Button>
                )}
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                <div className="sm:col-span-2 lg:col-span-2">
                  <FormField
                    label="Description"
                    value={row.product_description}
                    onChange={(v) => setItem(idx, "product_description", v)}
                    placeholder="Cumin Seeds (Cuminum cyminum)"
                    required
                  />
                </div>
                <FormField
                  label="HSN Code"
                  mono
                  value={row.hsn_code}
                  onChange={(v) => setItem(idx, "hsn_code", v)}
                  placeholder="09093129"
                />
                <FormField
                  label="Quantity"
                  numeric
                  value={row.quantity}
                  onChange={(v) => autoTotal(idx, "quantity", v)}
                  placeholder="1000"
                />
                <FormField
                  label="Unit"
                  value={row.unit}
                  onChange={(v) => setItem(idx, "unit", v)}
                  placeholder="KGS"
                />
                <FormField
                  label="Unit Price"
                  numeric
                  value={row.unit_price}
                  onChange={(v) => autoTotal(idx, "unit_price", v)}
                  placeholder="2.00"
                />
                <FormField
                  label="Total Value"
                  numeric
                  value={row.total_value}
                  onChange={(v) => autoTotal(idx, "total_value", v)}
                  placeholder="Auto-calculated"
                />
                <FormField
                  label="Net Weight (kg)"
                  numeric
                  value={row.net_weight}
                  onChange={(v) => setItem(idx, "net_weight", v)}
                  placeholder="1000"
                />
                <FormField
                  label="Gross Weight (kg)"
                  numeric
                  value={row.gross_weight}
                  onChange={(v) => setItem(idx, "gross_weight", v)}
                  placeholder="1050"
                />
                <FormField
                  label="No. of Packages"
                  numeric
                  value={row.package_count}
                  onChange={(v) => setItem(idx, "package_count", v)}
                  placeholder="20"
                />
                <FormField
                  label="Package Type"
                  value={row.package_type}
                  onChange={(v) => setItem(idx, "package_type", v)}
                  placeholder="Bags"
                />
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* Packing / freight summary */}
      <SectionCard title="Packing Summary & Freight">
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField
            label="Total Packages"
            numeric
            value={form.total_packages}
            onChange={set("total_packages")}
            placeholder="20"
          />
          <FormField
            label="Package Type"
            value={form.package_type_global}
            onChange={set("package_type_global")}
            placeholder="Bags"
          />
          <div />
          <FormField
            label="Total Net Weight (kg)"
            numeric
            value={form.total_net_weight}
            onChange={set("total_net_weight")}
            placeholder="1000"
          />
          <FormField
            label="Total Gross Weight (kg)"
            numeric
            value={form.total_gross_weight}
            onChange={set("total_gross_weight")}
            placeholder="1050"
          />
          <div />
          <FormField
            label="Freight"
            numeric
            value={form.freight}
            onChange={set("freight")}
            placeholder="200.00"
          />
          <FormField
            label="Insurance"
            numeric
            value={form.insurance}
            onChange={set("insurance")}
            placeholder="22.00"
          />
        </div>
      </SectionCard>

      {/* Declarations */}
      <SectionCard title="Declarations & Signatory">
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField
            label="Authorised Signatory Name"
            value={form.authorized_signatory_name}
            onChange={set("authorized_signatory_name")}
            placeholder="Rajesh Patel"
          />
          <FormField
            label="Designation"
            value={form.authorized_signatory_designation}
            onChange={set("authorized_signatory_designation")}
            placeholder="Director"
          />
          <FormField
            label="Place of Issue"
            value={form.place_of_issue}
            onChange={set("place_of_issue")}
            placeholder="Unjha"
          />
          <FormField
            label="Date of Issue"
            value={form.date_of_issue}
            onChange={set("date_of_issue")}
            type="date"
          />
        </div>
      </SectionCard>
    </>
  );
}
