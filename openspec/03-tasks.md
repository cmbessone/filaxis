# Tasks — FILAXIS PDF Processing Pipeline

## Work units

### WU1 — Project scaffold
- [x] pyproject.toml, .env.example, docker-compose.yml
- [x] CLAUDE.md at repo root
- [x] Package structure (filaxis/, tests/)

### WU2 — Config & logging
- [x] `filaxis/config.py` — pydantic-settings with all env vars
- [x] `filaxis/logging.py` — structured JSON logger

### WU3 — DB layer
- [x] `filaxis/db/engine.py` — SQLAlchemy engine + session factory
- [x] `filaxis/db/models.py` — Patient + DiagnosticReport ORM models

### WU4 — FHIR models
- [x] `filaxis/fhir/models.py` — Pydantic FHIR R5 DiagnosticReport + Observation
- [x] `filaxis/fhir/loinc.py` — LOINC code registry for CBC

### WU5 — Activities
- [x] `filaxis/activities/s3.py` — download_pdf_from_s3
- [x] `filaxis/activities/extraction.py` — extract_text_from_pdf (Docling)
- [x] `filaxis/activities/conversion.py` — convert_to_fhir (LLM)
- [x] `filaxis/activities/storage.py` — check_cache, store_report

### WU6 — Temporal workflow
- [x] `filaxis/workflows/pdf_pipeline.py` — PDFPipelineWorkflow
- [x] `filaxis/worker.py` — worker entry point

### WU7 — FastAPI
- [x] `filaxis/api/app.py` — app factory
- [x] `filaxis/api/auth.py` — JWT validation
- [x] `filaxis/api/routes/ingest.py` — POST /ingest
- [x] `filaxis/api/routes/patient.py` — GET /patients/{id}/reports
- [x] `filaxis/api/routes/physician.py` — GET /physician/low-wbc-patients

### WU8 — Tests
- [x] `tests/conftest.py` — fixtures (test DB, mock S3, mock LLM)
- [x] `tests/test_extraction.py`
- [x] `tests/test_conversion.py`
- [x] `tests/test_workflow.py`
- [x] `tests/test_api.py`

## Test plan
- [ ] unit: extraction activity with fixture PDF bytes
- [ ] unit: conversion activity with mock LLM returning known JSON
- [ ] unit: storage activity with in-memory SQLite
- [ ] integration/smoke: full workflow with mock S3 + mock LLM → verify DB row + FHIR shape
- [ ] integration: API endpoints with seeded DB

## Review workload forecast
~400–500 lines across pipeline; reviewable in a single pass. No file exceeds ~150 lines.
