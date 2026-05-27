# Proposal — FILAXIS PDF Processing Pipeline

## Problem
Filaxis uploads CBC (Complete Blood Count) lab results to S3 as unstructured PDFs (one per analysis).
The internal Data Platform (DP) requires structured FHIR R5 resources to power patient dashboards and
physician monitoring tools. There is no automated bridge between the two.

## Goals
- Parse CBC PDFs from S3 using Docling (text extraction) and an LLM (structured mapping).
- Produce valid FHIR R5 DiagnosticReport + Observation resources per PDF.
- Orchestrate the pipeline durably via Temporal so that failures are retried and progress is not lost.
- Cache processed results by PDF hash so OCR/LLM costs are paid at most once per unique document.
- Expose two query endpoints: patient CBC history (Use Case A) and physician low-WBC alert (Use Case B).

## Non-goals
- Frontend UI (the DP owns that).
- Non-CBC lab types.
- Real S3 infra for this deliverable (S3 access is injected via env; local files work for dev/test).
- Full FHIR server (we store FHIR JSON in our own DB and expose two purpose-built endpoints).

## User impact
- **Patients**: see their CBC history on the dashboard with correct, structured values.
- **Physicians**: immediately identify patients with WBC < 4500 /mm³ without manual PDF review.

## Risks
- LLM hallucination on numeric values → mitigated by strict JSON schema + unit validation.
- PDF format changes at Filaxis → Docling is format-agnostic; LLM prompt is instruction-based.
- OCR cost at scale → SHA-256 content hash prevents redundant calls.
- Reprocessing breaks existing data → workflow is idempotent; reprocess flag overwrites by PDF hash.

## Success criteria
- AC1: Given a valid hemograma PDF, the pipeline produces a FHIR R5 DiagnosticReport with all CBC observations populated and correct LOINC codes.
- AC2: Submitting the same PDF twice does not trigger a second LLM call (cache hit verified by log).
- AC3: Use Case A endpoint returns paginated, sortable CBC results for a patient with valid token.
- AC4: Use Case B endpoint returns only patients with WBC < 4500 /mm³ and rejects unauthorized tokens.
