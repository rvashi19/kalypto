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

## Limitations

The AI Document Verifier is an audit helper only. It does not provide legal advice, customs advice, or 100% verification accuracy. It does not submit anything to customs, DGFT, ICEGATE, banks, or government portals.

Scanned images require OCR to extract fields automatically. Until OCR is added, image uploads are accepted as supporting documents but need manual review.

CCR and incentive integrations are optional and depend on source-backed data already present in KALYPTO.
