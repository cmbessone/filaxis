import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from filaxis.activities.conversion import convert_to_fhir
from filaxis.activities.extraction import extract_text_from_pdf
from filaxis.activities.s3 import download_pdf
from filaxis.activities.storage import check_cache, store_report
from filaxis.config import settings
from filaxis.db.engine import init_db
from filaxis.logging import configure_logging, get_logger
from filaxis.workflows.pdf_pipeline import PDFPipelineWorkflow

log = get_logger(__name__)


async def _run() -> None:
    configure_logging()
    await init_db()

    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[PDFPipelineWorkflow],
        activities=[download_pdf, extract_text_from_pdf, convert_to_fhir, check_cache, store_report],
    )
    log.info("worker.start", task_queue=settings.temporal_task_queue)
    await worker.run()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
