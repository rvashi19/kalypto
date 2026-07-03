import * as React from "react";
import { cn } from "../lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-11 w-full rounded-lg border border-[#b7b9be] bg-white px-3.5 py-2 text-sm text-[#101214] transition-colors placeholder:text-[#42526e]/60 focus-visible:border-[#1868db] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1868db]/25 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Input.displayName = "Input";
