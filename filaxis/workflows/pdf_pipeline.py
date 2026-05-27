from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from filaxis.activities.s3 import download_pdf
    from filaxis.activities.extraction import extract_text_from_pdf
    from filaxis.activities.conversion import convert_to_fhir
    from filaxis.activities.storage import check_cache, store_report


@dataclass
class PDFPipelineInput:
    s3_key: str
    force: bool = False


@dataclass
class PDFPipelineResult:
    report_id: str | None
    cached: bool
    pdf_hash: str


_DEFAULT_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))
_LLM_RETRY = RetryPolicy(maximum_attempts=2, initial_interval=timedelta(seconds=10))


@workflow.defn
class PDFPipelineWorkflow:
    @workflow.run
    async def run(self, input: PDFPipelineInput) -> PDFPipelineResult:
        workflow.logger.info("pdf_pipeline.start", extra={"s3_key": input.s3_key, "force": input.force})

        # Step 1: Download PDF + compute hash
        download = await workflow.execute_activity(
            download_pdf,
            input.s3_key,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )

        # Step 2: Cache check (skip if force=True)
        if not input.force:
            cache = await workflow.execute_activity(
                check_cache,
                download.pdf_hash,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_DEFAULT_RETRY,
            )
            if cache.cached:
                workflow.logger.info("pdf_pipeline.cache_hit", extra={"pdf_hash": download.pdf_hash})
                return PDFPipelineResult(report_id=cache.report_id, cached=True, pdf_hash=download.pdf_hash)

        # Step 3: Extract text (Docling)
        extracted_text = await workflow.execute_activity(
            extract_text_from_pdf,
            download.pdf_bytes,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_DEFAULT_RETRY,
        )

        # Step 4: Convert to FHIR (LLM — pay-per-use, limited retries)
        conversion = await workflow.execute_activity(
            convert_to_fhir,
            extracted_text,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_LLM_RETRY,
        )

        # Step 5: Store result
        report_id = await workflow.execute_activity(
            store_report,
            args=[conversion, download.pdf_hash, input.s3_key],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=_DEFAULT_RETRY,
        )

        workflow.logger.info("pdf_pipeline.done", extra={"report_id": report_id})
        return PDFPipelineResult(report_id=report_id, cached=False, pdf_hash=download.pdf_hash)
