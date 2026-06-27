# Production Data Governance

KALYPTO must not show client-facing incentive or compliance answers unless the data is source-backed and reviewed.

## Rate Tables

Use the rate import flow for operator-managed incentive schedules such as RoDTEP, Duty Drawback AIR, and RoSCTL. Imported rows default to `pending`; client-facing tools only use rows where:

- `review_status` is `approved`
- `expires_at` is empty or in the future
- the HSN prefix matches the searched HSN

Required CSV columns:

```csv
scheme,hsn,rate,source,source_url,effective_date,version_stamp,confidence,review_status,reviewed_by,reviewed_at,expires_at,notes
```

Use official or operator-verified sources. Do not use model-generated rates.

## Compliance Requirements

Country Compliance Requirement Checker records must include official source references and human review metadata. Use `review_status: "approved"` only after an operator has checked the source wording.

The scraper supports:

- Plain public HTML pages
- Text pages
- Public PDFs with extractable text
- Firecrawl as an optional fallback for difficult pages

The scheduled refresh command checks approved sources for changes:

```bash
cd apps/api
python -m app.scripts.refresh_compliance_sources --limit-per-org 25
```

Changed sources are stored as review evidence. They should be reviewed before changing structured compliance requirements.

## Suggested Low-Cost Source Strategy

- Start with built-in HTTP/PDF scraping because it has no API cost.
- Add Firecrawl only for pages that block normal extraction or need JavaScript rendering.
- Add a search/discovery API only if operators need help finding official sources at scale.
- Avoid expensive proxy networks unless a critical official source blocks server-side fetching.

## Client-Safe Rule

When verified data is missing, the product should say so and ask for operator review. It should never fill gaps with AI guesses.
