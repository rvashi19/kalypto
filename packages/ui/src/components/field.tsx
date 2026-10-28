import * as React from "react";
import { cn } from "../lib/utils";
import { Label } from "./label";

export interface FieldControlProps {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  required?: boolean;
}

export interface FieldProps {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  className?: string;
  /** Render prop receives the a11y props to spread on the control; or pass a single element and they are cloned in. */
  children: React.ReactElement | ((props: FieldControlProps) => React.ReactNode);
}

export function Field({ label, hint, error, required, className, children }: FieldProps) {
  const id = React.useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  const controlProps: FieldControlProps = {
    id,
    "aria-describedby": describedBy,
    "aria-invalid": error ? true : undefined,
    required: required || undefined,
  };

  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id}>
        {label}
        {required && (
          <span className="ml-0.5 text-danger-fg" aria-hidden="true">
            *
          </span>
        )}
      </Label>
      {typeof children === "function"
        ? children(controlProps)
        : React.cloneElement(children, controlProps)}
      {hint && (
        <p id={hintId} className="text-xs text-ink-3">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-xs font-medium text-danger-fg">
          {error}
        </p>
      )}
    </div>
  );
}
