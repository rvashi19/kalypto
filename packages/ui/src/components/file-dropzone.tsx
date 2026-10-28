import * as React from "react";
import { cn } from "../lib/utils";

export interface FileDropzoneProps {
  /** Comma-separated extensions and/or MIME types, as for <input accept>. */
  accept?: string;
  maxBytes?: number;
  file: File | null;
  onFileChange: (file: File | null) => void;
  /** External error (e.g. from the server); validation errors are shown too. */
  error?: string;
  label?: string;
  disabled?: boolean;
  id?: string;
  "aria-describedby"?: string;
}

function matchesAccept(file: File, accept?: string): boolean {
  if (!accept) return true;
  const name = file.name.toLowerCase();
  return accept.split(",").some((raw) => {
    const a = raw.trim().toLowerCase();
    if (!a) return false;
    if (a.startsWith(".")) return name.endsWith(a);
    if (a.endsWith("/*")) return file.type.startsWith(a.slice(0, -1));
    return file.type === a;
  });
}

export function FileDropzone({
  accept,
  maxBytes,
  file,
  onFileChange,
  error,
  label = "Choose a file or drop it here",
  disabled,
  id,
  "aria-describedby": describedBy,
}: FileDropzoneProps) {
  const autoId = React.useId();
  const inputId = id ?? autoId;
  const errId = `${inputId}-error`;
  const [localError, setLocalError] = React.useState<string>();
  const [dragging, setDragging] = React.useState(false);
  const shown = localError ?? error;

  const take = (f: File | undefined) => {
    if (!f) return;
    if (!matchesAccept(f, accept)) {
      setLocalError(`Unsupported file type. Allowed: ${accept}.`);
      return;
    }
    if (maxBytes && f.size > maxBytes) {
      setLocalError(
        `File is too large. Maximum size is ${(maxBytes / 1024 / 1024).toFixed(1)} MB.`
      );
      return;
    }
    setLocalError(undefined);
    onFileChange(f);
  };

  return (
    <div>
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!disabled) take(e.dataTransfer.files[0]);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-1 rounded-card border-2 border-dashed px-4 py-8 text-center text-sm transition-colors focus-within:ring-2 focus-within:ring-brand focus-within:ring-offset-2",
          dragging
            ? "border-brand bg-brand-soft"
            : "border-line-strong bg-surface hover:bg-surface-2",
          shown && "border-danger-fg",
          disabled && "cursor-not-allowed opacity-50"
        )}
      >
        <span className="font-medium text-ink">{file ? file.name : label}</span>
        <span className="text-xs text-ink-3">
          {file
            ? `${(file.size / 1024).toFixed(0)} KB`
            : [accept, maxBytes && `up to ${(maxBytes / 1024 / 1024).toFixed(0)} MB`]
                .filter(Boolean)
                .join(" · ")}
        </span>
        <input
          id={inputId}
          type="file"
          accept={accept}
          disabled={disabled}
          className="sr-only"
          aria-invalid={shown ? true : undefined}
          aria-describedby={
            [describedBy, shown ? errId : undefined].filter(Boolean).join(" ") || undefined
          }
          onChange={(e) => {
            take(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </label>
      {shown && (
        <p id={errId} role="alert" className="mt-1.5 text-xs font-medium text-danger-fg">
          {shown}
        </p>
      )}
    </div>
  );
}
