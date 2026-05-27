# Spec — FILAXIS PDF Processing Pipeline

## Scope
PDF ingestion pipeline only. Receives an S3 key (or local path), produces a stored FHIR R5
DiagnosticReport, and exposes two read endpoints. Auth, pagination, and sorting are in scope.
Frontend, FHIR server, and non-CBC types are out of scope.

## Functional requirements

### Pipeline
- FR1: The pipeline accepts an S3 object key as input and downloads the PDF bytes.
- FR2: Docling extracts raw text from the PDF bytes without loss.
- FR3: An LLM maps the raw text to a FHIR R5 DiagnosticReport with Observation resources, each carrying a LOINC code and `valueQuantity` with value and unit.
- FR4: The pipeline computes SHA-256 of the PDF bytes and skips FR2–FR3 if a report with that hash already exists (cache hit).
- FR5: The pipeline is idempotent: re-running with the same key returns the cached report; running with `force=True` overwrites.
- FR6: All pipeline steps are Temporal activities; the workflow survives worker restarts.

### Storage
- FR7: Each DiagnosticReport is stored as a JSONB blob alongside denormalized columns: `patient_filaxis_id`, `report_date`, `wbc_count`, `pdf_hash`.
- FR8: Patients are upserted from the data extracted in the PDF (Filaxis patient ID + name).

### API — Use Case A
- FR9: `GET /patients/{patient_id}/reports` returns CBC reports for that patient, paginated (default 10, max 100) and sortable by `report_date` asc/desc.
- FR10: The endpoint validates a Bearer JWT; the token subject must match `patient_id` (or carry a `physician` role).

### API — Use Case B
- FR11: `GET /physician/low-wbc-patients` returns a list of `{ patient_id, patient_name, wbc_count, report_date }` where `wbc_count < 4500` (most recent report per patient).
- FR12: The endpoint requires a Bearer JWT with `physician` role.

### Ingestion trigger
- FR13: `POST /ingest` accepts `{ s3_key, force }` and starts (or signals) a Temporal workflow. Returns `{ workflow_id, run_id }`.

## Validation rules
- VR1: `wbc_count` must be a positive number; reject or flag if LLM returns null or negative.
- VR2: LOINC codes must match the expected set for CBC (see `filaxis/fhir/loinc.py`).
- VR3: JWT signature validated with HS256 against `JWT_SECRET` env var; expired tokens rejected.

## Acceptance criteria
- AC1: `POST /ingest` with a valid PDF S3 key → 202 response + workflow started → DiagnosticReport stored within workflow completion.
- AC2: Second `POST /ingest` with same key → 202 response + log shows `cache_hit=True` + no LLM call made.
- AC3: `GET /patients/{patient_id}/reports?sort=report_date&order=desc&page=1&page_size=5` → returns correct subset, sorted.
- AC4: `GET /physician/low-wbc-patients` with patient token → 403.
- AC5: All CBC observations in the stored report carry valid LOINC codes and numeric `valueQuantity`.
