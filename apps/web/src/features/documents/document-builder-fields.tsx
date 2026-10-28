import { Alert, Field, Input, Select } from "@repo/ui";

const HIGHLIGHT_CLASS = "border-warning-border ring-1 ring-warning-border";
const HIGHLIGHT_HINT = "Not found in the uploaded document. Please fill in.";

export function FormField({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  required,
  highlight,
  mono,
  numeric,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
  highlight?: boolean;
  mono?: boolean;
  numeric?: boolean;
}) {
  const cls = [
    highlight ? HIGHLIGHT_CLASS : "",
    mono ? "font-mono" : "",
    numeric ? "tabular-nums" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <Field label={label} required={required} hint={highlight ? HIGHLIGHT_HINT : undefined}>
      <Input
        type={type}
        inputMode={numeric ? "decimal" : undefined}
        className={cls || undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </Field>
  );
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  highlight,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  highlight?: boolean;
}) {
  return (
    <Field label={label} hint={highlight ? HIGHLIGHT_HINT : undefined}>
      <Select
        className={highlight ? HIGHLIGHT_CLASS : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </Select>
    </Field>
  );
}

export function ValidationIssues({
  issues,
}: {
  issues: { code: string; message: string; severity: string }[];
}) {
  if (!issues.length) return null;
  return (
    <div className="space-y-2">
      {issues.map((i) => (
        <Alert
          key={i.code}
          tone={i.severity === "error" ? "danger" : "warning"}
          title={<span className="font-mono">{i.code}</span>}
        >
          {i.message}
        </Alert>
      ))}
    </div>
  );
}
