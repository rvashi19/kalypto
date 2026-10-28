import * as React from "react";
import { Button } from "./button";

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive,
  loading,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const ref = React.useRef<HTMLDialogElement>(null);
  const opener = React.useRef<Element | null>(null);
  const titleId = React.useId();

  React.useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      opener.current = document.activeElement;
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  // Return focus to the trigger when closed (native dialog does this too; explicit for safety).
  const handleClose = () => {
    if (opener.current instanceof HTMLElement) opener.current.focus();
    if (open) onCancel();
  };

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={handleClose}
      onCancel={(e) => {
        e.preventDefault();
        if (!loading) onCancel();
      }}
      className="w-[min(440px,calc(100%-32px))] rounded-card border border-line bg-surface p-0 text-ink shadow-pop backdrop:bg-[rgba(16,18,20,0.5)]"
    >
      <div className="space-y-2 p-5">
        <h2 id={titleId} className="text-base font-semibold">
          {title}
        </h2>
        {description && <div className="text-sm text-ink-2">{description}</div>}
      </div>
      <div className="flex justify-end gap-2 border-t border-line px-5 py-3">
        <Button variant="secondary" onClick={onCancel} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button variant={destructive ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}
