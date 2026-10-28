# AI Document Verifier

The AI Document Verifier is a pre-filing and pre-claim audit helper for export shipment documents. It lets a user create a verification run, upload shipment documents, extract structured fields with evidence, compare those fields across documents, and save a report for review.

It is not a customs filing system, legal opinion, or guarantee of claim eligibility.

## Supported Documents

The verifier can work with:

- Commercial invoice
- Proforma invoice
- Packing list
- Invoice-cum-packing list
- Shipping bill / bill of export
- Bill of lading
- Air waybill
- Certificate of origin
- Insurance certificate
- Fumigation certificate
- Phytosanitary certificate
- Inspection certificate
- Purchase order
- Letter of credit
- Export quote / costing sheet
- Other supporting files

## Supported File Formats

Current upload formats:

- PDF
- XLSX
- CSV
- JPG / JPEG / PNG

PDF text and tables are extracted with `pdfplumber`. XLSX files are read with `openpyxl`. CSV files are read as text. Image files are accepted but are marked for manual verification unless OCR is added later.

## Extraction Flow

1. The user creates a verification run.
2. The user uploads one or more files.
3. Files are stored through the existing KALYPTO storage abstraction.
4. The backend extracts text/tables from each file.
5. If an AI provider is configured, the verifier asks for strict JSON field extraction.
6. If AI is unavailable or fails, the verifier uses deterministic pattern extraction for common export fields.
7. Every extracted field is stored with evidence:
   - document id
   - document type
   - page number when known
   - table reference when known
   - raw value
   - normalized value
   - confidence score
   - evidence excerpt

The verifier does not invent missing values. Missing or unreadable values remain absent or low-confidence.

## Verification Flow

After extraction, the user runs verification. The verifier compares normalized values first, while preserving raw values for evidence.

Implemented checks include:

- HSN consistency across documents
- Invoice number consistency
- Product description consistency
- Quantity and unit consistency
- Net and gross weight consistency
- Package count and package type consistency
- Invoice/FOB/CIF value consistency with numeric tolerance
- Incoterm consistency
- Port and destination consistency
- Country of origin/destination consistency
- Container and seal number consistency
- Optional CCR-backed required certificate presence checks when approved CCR data exists

Issues are stored with severity, status, evidence, and related document ids. Users can mark issues as resolved or ignored.

## Verification Score

After verification the verifier computes a **Document Verification Score** (0–100) plus four
category scores. All weights live in one place: `app/services/document_verifier_scoring.py`
(`SCORING_WEIGHTS`).

Score bands:

- 90–100: Strong consistency — manual review still recommended
- 75–89: Mostly consistent — review flagged issues
- 50–74: Needs correction before filing/claiming
- 0–49: High risk — do not file/claim before review

Category scores:

1. **Document Completeness** — reduced when expected/requested documents are missing
   (critical −25, high −15, medium −7, low −2 per missing document).
2. **Field Consistency** — reduced per issue by severity (critical −25, high −15,
   medium −7, low −2, info −0).
3. **Extraction Confidence** — reduced when extracted fields fall below 60% confidence
   (critical fields −10, other fields −5).
4. **Claim/Filing Risk** — combines issue and missing-document penalties.

The overall score subtracts all penalties from 100 and is clamped to 0–100. Readiness
statuses: `ready_for_manual_review`, `needs_minor_review`, `needs_corrections`,
`high_risk_do_not_file_without_review`, and `waiting_for_required_documents` (set whenever
a critical expected document is missing). The report stores a `score_explanation` and a
per-penalty breakdown so users can see exactly why the score was reduced.

### Resolved vs ignored issues

- **Resolved** issues carry no penalty (the underlying problem was fixed).
- **Ignored** issues remain visible and carry **half** penalty — they are treated as
  accepted risk, not as fixed.
- Reviewer decisions (resolved/ignored) are carried over across re-verifications for
  issues that reappear with the same signature.

## Requested / Missing Documents

Verification builds a requested-document list from two sources:

1. A core expected pack (Commercial Invoice, Shipping Bill, Packing List, BL/AWB,
   Certificate of Origin, LC/PO) with priorities and reasons.
2. CCR source-backed requirements (e.g. Phytosanitary Certificate) when approved CCR data
   exists for the destination.

Each entry records `document_type`, `reason`, `priority`, `related_fields`, `required_for`
(filing / claim / consistency / CCR / optional_review), and `status` (missing / uploaded).
Equivalents are honored (an Air Waybill satisfies the BL slot; an Invoice-cum-Packing List
satisfies both invoice and packing-list slots). The list is stored in the report
`summary_json` — no extra table.

## Re-verification

Users can upload more documents at any time, re-run extraction, and re-run verification.
Each verification regenerates the latest issue set and report, recalculates the score, and
updates requested-document statuses (missing → uploaded). Resolved/ignored decisions are
carried over by issue signature. Only the latest report is kept; historical
verification versions are not retained (known limitation).

## Report

The verifier stores a report summary with issue counts and can generate a PDF report using the existing ReportLab stack.

Recommended report language:

- Review required
- Likely consistent
- Mismatch found
- Missing field
- Needs manual verification

Do not describe a report as approved for filing.

## Security And Privacy

Uploaded files may contain sensitive commercial data.

The verifier:

- Enforces tenant-scoped access checks.
- Uses the existing storage abstraction.
- Restricts file types.
- Enforces file size limits through `DOCUMENT_VERIFIER_MAX_FILE_MB`.
- Does not log full document text or AI prompts in production code paths.

## Environment

```bash
DOCUMENT_VERIFIER_MAX_FILE_MB=20
DOCUMENT_VERIFIER_ALLOWED_TYPES=pdf,xlsx,csv,jpg,jpeg,png
AI_PROVIDER=auto
OPENAI_API_KEY=
GROQ_API_KEY=
```

Uploaded files use KALYPTO's existing storage abstraction: local `UPLOAD_DIR` in development,
or the configured R2/S3-compatible backend in production.

## Deployment

The verifier tables ship in Alembic migration `0020_document_verifier`. Production databases
must be migrated before (or as part of) deploying this feature:

```bash
cd apps/api
alembic upgrade head
```

On Render this happens automatically — `scripts/start-render.sh` runs `alembic upgrade head`
on startup. For any manually managed environment, run the command above against the
production `DATABASE_URL` before serving traffic.

## Limitations

The AI Document Verifier is an audit helper only. It does not provide legal advice, customs advice, or 100% verification accuracy. It does not submit anything to customs, DGFT, ICEGATE, banks, or government portals.

Scanned images require OCR to extract fields automatically. Until OCR is added, image uploads are accepted as supporting documents but need manual review.

CCR and incentive integrations are optional and depend on source-backed data already present in KALYPTO.
