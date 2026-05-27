from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from temporalio.client import Client

from filaxis.config import settings
from filaxis.logging import get_logger
from filaxis.workflows.pdf_pipeline import PDFPipelineInput, PDFPipelineWorkflow

router = APIRouter()
log = get_logger(__name__)


class IngestRequest(BaseModel):
    s3_key: str
    force: bool = False


class IngestResponse(BaseModel):
    workflow_id: str
    run_id: str


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest(body: IngestRequest) -> IngestResponse:
    """Start a PDF pipeline workflow for the given S3 key."""
    workflow_id = f"pdf-{body.s3_key.replace('/', '-')}"

    try:
        client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
        handle = await client.start_workflow(
            PDFPipelineWorkflow.run,
            PDFPipelineInput(s3_key=body.s3_key, force=body.force),
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except Exception as exc:
        log.error("ingest.temporal_error", error=str(exc), s3_key=body.s3_key)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Temporal unavailable") from exc

    log.info("ingest.started", workflow_id=workflow_id, s3_key=body.s3_key, force=body.force)
    return IngestResponse(workflow_id=handle.id, run_id=handle.result_run_id or "")
