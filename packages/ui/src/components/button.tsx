import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../lib/utils";
import { Spinner } from "./spinner";

// Note: avoid the literal class "text-white" - the legacy shim in index.css rewrites it.
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control border text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "border-brand bg-brand text-[#ffffff] hover:bg-brand-hover active:bg-brand-hover",
        secondary: "border-line-strong bg-surface text-ink hover:bg-surface-2 active:bg-line",
        ghost: "border-transparent bg-transparent text-brand hover:bg-brand-soft active:bg-brand-soft",
        danger: "border-danger-fg bg-danger-fg text-[#ffffff] hover:brightness-90 active:brightness-75",
      },
      size: {
        sm: "h-8 px-3",
        md: "h-10 px-4",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "default";
type ButtonSize = "sm" | "md" | "default" | "lg";

/** Class string for buttons and for react-router <Link>s that should look like buttons. */
export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md", className?: string): string {
  return cn(
    buttonVariants({
      variant: variant === "default" ? "primary" : variant,
      size: size === "default" || size === "lg" ? "md" : size,
    }),
    className
  );
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** "default" is a legacy alias of "primary". */
  variant?: ButtonVariant;
  /** "default" and "lg" are legacy aliases of "md". */
  size?: ButtonSize;
  loading?: boolean;
}

export type { VariantProps };

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading = false, disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      className={buttonClasses(variant, size, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  )
);
Button.displayName = "Button";
