# KALYPTO design direction (approved 2026-10-26)

Calm, document-centric workspace: precise, trustworthy, easy to scan for problems.

## Tokens
- **Type:** Inter for everything; JetBrains Mono (or `ui-monospace`) for HSN codes and reference numbers. Page title 24/32 semibold, section title 16 semibold, body 14/1.5, label 12 medium. Nothing below 12px.
- **Color roles:** bg `#f6f7f9`, surface `#fff`, surface-2 `#f0f2f5`, border `#dfe3e8`, border-strong `#c3c9d2`, text `#14181f`, text-2 `#4a5568`, text-3 `#6b7585`, brand `#1868db` (hover `#1458bb`, soft `#e9f1fd`), ring = brand. Nav `#101214`, nav-text `#c7ccd4`.
- **Status triples (fg / bg / border):** success `#1f7a4d / #e8f5ee / #b5dec8`, warning `#8a5a00 / #fff5e0 / #f2d38f`, danger `#b42318 / #fdeceb / #f5c2bd`, info = brand / brand-soft / `#bcd4f6`. Status always shows icon + word, never color alone.
- **Spacing:** 4px scale (4, 8, 12, 16, 24, 32). **Radii:** 6 (buttons, inputs), 8 (small panels, alerts), 12 (cards), pill only for badges.

## Layout & navigation
- Dark left sidebar, 232px, grouped: Workspace (Dashboard, Shipments, Document verifier, Document builder), Lookup (HSN finder, Incentive finder, Export quote), Compliance (Country checker). Org name on top, role + sign out at the bottom. Active item: lighter background + 2px brand left bar, `aria-current="page"`.
- Below 860px: dark top bar with a Menu button that opens the same nav as a drawer.
- Page: breadcrumb → single `<h1>` with key facts → actions right-aligned. Content max 1120px. Wide screens may use a 320px summary column; mobile is one column.

## Components
Button (primary / secondary / ghost / danger; sm/md; loading), Field (label + control + hint + error with `htmlFor`, `aria-describedby`, `aria-invalid`, required marker), Input, Select, Textarea, FileDropzone (type/size validation), Alert (info/success/warning/danger with correct `role`), Badge, Card, Table, Tabs (ARIA tabs), Stepper (compact "Step n of m" on mobile), ConfirmDialog, EmptyState, Skeleton, QueryState (loading / empty / error + retry), PageHeader.

## Interaction states
Every control: hover, `focus-visible` 2px brand ring with 2px offset, active, disabled (50% opacity, not-allowed), loading (spinner, locked), error.

Reference mockup: shipment verification report, desktop and mobile.
