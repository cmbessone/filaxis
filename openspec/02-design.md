# Design — FILAXIS PDF Processing Pipeline

## Architecture sketch

```
S3 Bucket (Filaxis)
      │  PUT event / webhook
      ▼
┌─────────────────────┐
│  FastAPI  /ingest   │  POST { s3_key, force }
│  (trigger layer)    │──────────────────────────►  Temporal Client
└─────────────────────┘                                    │
                                                           │  start_workflow()
                                                           ▼
                                              ┌─────────────────────────┐
                                              │  PDFPipelineWorkflow     │
                                              │  ┌───────────────────┐  │
                                              │  │ download_from_s3  │  │ activity
                                              │  ├───────────────────┤  │
                                              │  │ check_cache       │  │ activity (DB lookup)
                                              │  ├───────────────────┤  │
                                              │  │ extract_text      │  │ activity (Docling)
                                              │  ├───────────────────┤  │
                                              │  │ convert_to_fhir   │  │ activity (LLM / Claude)
                                              │  ├───────────────────┤  │
                                              │  │ store_report      │  │ activity (DB upsert)
                                              │  └───────────────────┘  │
                                              └─────────────────────────┘
                                                           │
                                                      SQLite / PG DB
                                                           │
                                              ┌────────────▼────────────┐
                                              │  FastAPI query layer     │
                                              │  GET /patients/{id}/... │
                                              │  GET /physician/low-wbc │
                                              └─────────────────────────┘
```

## Component responsibilities

| Component | Responsibility |
|---|---|
| `activities/s3.py` | Download PDF bytes from S3 (or local FS in dev) |
| `activities/extraction.py` | Docling PDF→text; returns clean string |
| `activities/conversion.py` | LLM call (Claude) with FHIR schema; returns `DiagnosticReport` dict |
| `activities/storage.py` | Upsert Patient + DiagnosticReport; write-cache |
| `workflows/pdf_pipeline.py` | Orchestrate activities; enforce cache logic |
| `api/routes/ingest.py` | Trigger workflow via Temporal client |
| `api/routes/patient.py` | Use Case A — patient CBC history |
| `api/routes/physician.py` | Use Case B — low WBC patient list |
| `api/auth.py` | JWT decode + role enforcement |

## Data model

```sql
CREATE TABLE patients (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filaxis_id  TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT now()
);

CREATE TABLE diagnostic_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id),
    pdf_hash        TEXT UNIQUE NOT NULL,   -- SHA-256; cache key
    s3_key          TEXT,
    report_date     TIMESTAMP,
    wbc_count       REAL,                  -- denormalized for fast WBC filter
    fhir_resource   TEXT NOT NULL,         -- full FHIR R5 DiagnosticReport JSON
    status          TEXT DEFAULT 'final',
    created_at      TIMESTAMP DEFAULT now(),
    updated_at      TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_dr_patient_date ON diagnostic_reports(patient_id, report_date DESC);
CREATE INDEX idx_dr_wbc ON diagnostic_reports(wbc_count);
```

The `wbc_count` denormalization is deliberate: Use Case B does `WHERE wbc_count < 4500` on every
physician page load. Parsing JSONB on every row would be slow and non-portable.

## API contracts

### POST /ingest
```json
Request:  { "s3_key": "67505.43739.pdf", "force": false }
Response: { "workflow_id": "pdf-67505.43739", "run_id": "abc123", "cached": false }
```

### GET /patients/{patient_id}/reports
```
Query params: page (int, default 1), page_size (int, default 10, max 100),
              sort (report_date), order (asc|desc)
Response: {
  "total": 3,
  "page": 1,
  "items": [ { "report_id": "...", "report_date": "...", "wbc_count": 4950, "fhir_resource": {...} } ]
}
```

### GET /physician/low-wbc-patients
```
Response: [
  { "patient_id": "...", "patient_name": "...", "wbc_count": 4200, "report_date": "..." }
]
```

## Key design decisions

### Why Temporal?
Durable execution: if the worker crashes after Docling but before the LLM call, Temporal replays
from the last persisted activity result. No data is lost and the LLM is not called twice for the
same step in the same run.

### Caching strategy
SHA-256 of the raw PDF bytes is the cache key. The check happens in `check_cache` activity (DB read)
before any paid API call. `force=True` bypasses and overwrites. This directly addresses the
"OCR is pay-per-use" pain point.

### Reprocessing
Re-trigger with `force=True` and a new Temporal workflow run. The `store_report` activity does an
upsert keyed on `pdf_hash`, so data consistency is maintained: either the old report stays (no
force) or the new one atomically replaces it (force).

### REST over GraphQL
Use Cases A and B have fixed, well-understood shapes. REST with query params covers pagination,
sorting, and filtering without the added complexity of a GraphQL schema, resolver layer, and
N+1 query risk. If the DP later needs flexible cross-resource queries, a GraphQL layer can be
added on top of the same DB.

### How workflows start
The Temporal workflow is started via the Temporal Python SDK client inside the `/ingest` endpoint.
In production, an S3 event notification would POST to `/ingest` via a Lambda or EventBridge rule.
This decouples S3 from Temporal and makes the trigger testable without AWS.

### Authentication
HS256 JWT. The `sub` claim holds `patient_id`; a `role` claim distinguishes `patient` vs `physician`.
Use Case A checks `sub == patient_id OR role == physician`. Use Case B checks `role == physician`.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM returns wrong numeric value | Strict Pydantic schema on LLM output; unit test with known PDFs |
| Docling fails on unusual PDF encoding | Retry activity (3x with backoff); alert on final failure |
| Temporal server unavailable | `/ingest` returns 503; caller retries; no data written |
| JWT secret rotation | Env var; restart worker + API; tokens expire (1h default) |
