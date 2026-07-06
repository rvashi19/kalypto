# How to Feed CCR Official Compliance Sources

CCR uses official government or regulatory sources as the source of truth. AI is only used to extract and summarize requirement cards from those official sources. Do not feed blogs, consultants, aggregators, freight-forwarder articles, private compliance sites, or random scraped text as authority.

## A. Add Official Source URLs From The App

Open the Country Compliance Checker as an organization owner and use **Official sources (admin)**.

Example:

- Country: USA
- Category: food/agri
- Source URL: `https://www.fda.gov/food/food-imports-exports`
- Source type: `html`
- Authority name: US FDA
- Authority level: `official`
- Refresh frequency days: `30`
- Active: enabled

The backend rejects non-whitelisted domains. Add extra allowed domains only for official government/regulatory hosts that are safe for this organization to fetch.

## B. Add Spreadsheet/PDF Sources

Use the same admin form for official document URLs.

Example structure:

- Country: India
- Category: food/agri
- Source URL: official government PDF/XLSX/CSV URL
- Source type: `pdf`, `xlsx`, or `csv`
- Authority name: issuing government/regulatory body
- Authority level: `official`

Only use real official URLs already known to the project or added to `COMPLIANCE_ALLOWED_DOMAINS`. Do not invent government file URLs.

## C. Supported Source Types

CCR source registry creation accepts:

- `html`
- `pdf`
- `xlsx`
- `csv`

## D. Run The Seed Script

From the API app:

```bash
cd apps/api
python -m app.scripts.seed_compliance_sources
```

To seed one organization by slug:

```bash
cd apps/api
python -m app.scripts.seed_compliance_sources <org-slug>
```

The script is idempotent. It reports `created`, `updated`, `skipped`, and `total`, and it does not duplicate an existing `(tenant, country, source_url)` source.

Seeded sources are a vetted starting set for India, USA, Canada, UK, EU, and UAE. They do not imply full country coverage.

## E. Run Refresh

Use the admin UI buttons:

- **Refresh this source**: queues a retrieval job for one source.
- **Refresh due sources**: runs sources whose refresh frequency window has elapsed.

Scheduler endpoint:

```http
POST /api/v1/compliance/refresh-due?tenant_id=<organization-id>
X-Admin-Cron-Token: <ADMIN_CRON_TOKEN>
```

Admin endpoint for a single source:

```http
POST /api/v1/compliance/sources/<source-id>/refresh
```

After refresh, the UI displays job status, pages/files fetched, checksum status, parser used, extracted requirement count, pending review count, and any error message.

## F. Review Extracted Cards

AI-extracted requirement cards go to pending review. They are not used in CCR answers until an admin approves them.

- Pending cards are hidden from normal CCR answers.
- Approved cards become reusable source-backed CCR guidance.
- Rejected cards remain hidden from normal CCR answers.

## G. Warning

Use official URLs/documents first, then review extracted cards. CCR must not invent sources, treat random scraped text as truth, or bypass authentication, CAPTCHA, paywalls, access controls, or site restrictions.
