import { cn } from "../lib/utils";

export interface StepperStep {
  id: string;
  label: string;
  disabled?: boolean;
  /** Overrides the default "every step before the current one is done". */
  done?: boolean;
}

export interface StepperProps {
  steps: StepperStep[];
  /** Id of the current step. */
  current: string;
  onStepClick?: (id: string) => void;
  label?: string;
  className?: string;
}

export function Stepper({ steps, current, onStepClick, label = "Progress", className }: StepperProps) {
  const index = Math.max(0, steps.findIndex((s) => s.id === current));
  return (
    <nav aria-label={label} className={className}>
      <p className="text-sm font-medium text-ink sm:hidden">
        Step {index + 1} of {steps.length}: <span className="text-ink-2">{steps[index]?.label}</span>
      </p>
      <ol className="mt-2 flex gap-1 sm:mt-0 sm:gap-2">
        {steps.map((s, i) => {
          const isCurrent = i === index;
          const done = s.done ?? i < index;
          return (
            <li key={s.id} className="flex-1">
              <button
                type="button"
                aria-current={isCurrent ? "step" : undefined}
                aria-disabled={s.disabled || undefined}
                onClick={() => !s.disabled && onStepClick?.(s.id)}
                className={cn(
                  "flex min-h-11 w-full items-center justify-center gap-2 rounded-control border px-2 py-2 text-left text-sm font-medium sm:justify-start sm:px-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2",
                  isCurrent ? "border-brand bg-brand-soft text-brand" : "border-line bg-surface text-ink-2",
                  s.disabled && "cursor-not-allowed opacity-50"
                )}
              >
                <span className="font-mono text-xs">{done ? "Done" : i + 1}</span>
                {/* Below sm only the number shows; the "Step n of m" line above names the current step. */}
                <span className="sr-only sm:not-sr-only">{s.label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
