import type { Config } from "tailwindcss";

const tone = (name: string) => ({
  fg: `var(--k-${name}-fg)`,
  bg: `var(--k-${name}-bg)`,
  border: `var(--k-${name}-border)`
});

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        border: "hsl(var(--border))",
        ring: "hsl(var(--ring))",
        canvas: "var(--k-canvas)",
        surface: { DEFAULT: "var(--k-surface)", 2: "var(--k-surface-2)" },
        line: { DEFAULT: "var(--k-line)", strong: "var(--k-line-strong)" },
        ink: { DEFAULT: "var(--k-ink)", 2: "var(--k-ink-2)", 3: "var(--k-ink-3)" },
        brand: { DEFAULT: "var(--k-brand)", hover: "var(--k-brand-hover)", soft: "var(--k-brand-soft)" },
        nav: { DEFAULT: "var(--k-nav)", text: "var(--k-nav-text)" },
        success: tone("success"),
        warning: tone("warning"),
        danger: tone("danger"),
        info: tone("info")
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"]
      },
      borderRadius: {
        control: "6px",
        panel: "8px",
        card: "12px"
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,18,20,0.06), 0 0 0 1px rgba(16,18,20,0.02)",
        pop: "0 8px 24px rgba(16,18,20,0.16)"
      }
    }
  },
  plugins: []
};

export default config;
