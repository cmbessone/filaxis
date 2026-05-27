# FILAXIS — PDF Processing Pipeline

Processes CBC (Complete Blood Count) lab PDFs from S3 into FHIR R5 resources using
**Temporal** (orchestration) + **Docling** (PDF extraction) + **Claude** (structured mapping).

## Architecture

```
S3 PDF → Temporal Workflow → Docling extract → LLM → FHIR R5 DiagnosticReport → DB
                                                                                    ↓
                                                                   FastAPI query endpoints
```

See `openspec/02-design.md` for the full architecture diagram and key design decisions.

## Quick start

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY, JWT_SECRET, and optionally AWS credentials

# Start Temporal + API + Worker
docker-compose up

# Or run locally:
pip install -e ".[dev]"
uvicorn filaxis.api.app:app --reload &
python -m filaxis.worker &
```

## Ingest a PDF

```bash
# Trigger pipeline for an S3 key
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"s3_key": "67505.43739.818013.409724.pdf", "force": false}'

# Local dev: use a file path as s3_key
curl -X POST http://localhost:8000/ingest \
  -d '{"s3_key": "/path/to/hemograma_ficticio_1.pdf"}'
```

## Query endpoints

```bash
# Use Case A — patient CBC history
curl http://localhost:8000/patients/PAT-00123/reports?order=desc \
  -H "Authorization: Bearer <patient-or-physician-jwt>"

# Use Case B — physician low-WBC monitoring
curl http://localhost:8000/physician/low-wbc-patients \
  -H "Authorization: Bearer <physician-jwt>"
```

## Generate test JWTs (dev only)

```python
from jose import jwt
token = jwt.encode({"sub": "PAT-00123", "role": "patient"}, "dev-secret-change-in-production")
```

## Run tests

```bash
pytest tests/ -v
```

## Key design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Orchestration | Temporal | Durable execution; retry per-activity; reprocess by re-running workflow |
| PDF extraction | Docling | Format-agnostic; handles layout-heavy PDFs without custom regex |
| LLM | Claude (Anthropic) | Reliable JSON output; easy to version the prompt |
| Caching | SHA-256 of PDF bytes | Same file → same hash → skip LLM call entirely |
| API style | REST | Fixed use-case shapes; no GraphQL N+1 risk; simpler auth middleware |
| Auth | HS256 JWT | Stateless; `sub` = patient_id; `role` = patient|physician |
| Storage | SQLite / PG (SQLAlchemy) | `wbc_count` denormalized for fast Use Case B filter |

## Project structure

```
filaxis/
├── activities/       # Temporal activities (S3, Docling, LLM, DB)
├── workflows/        # PDFPipelineWorkflow
├── api/              # FastAPI app + routes + auth
├── db/               # SQLAlchemy models + engine
└── fhir/             # FHIR R5 Pydantic models + LOINC registry
openspec/             # SDD artifacts (proposal, spec, design, tasks)
tests/                # pytest suite
```
