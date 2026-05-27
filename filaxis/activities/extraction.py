import tempfile
from pathlib import Path

from temporalio import activity

from filaxis.logging import get_logger

log = get_logger(__name__)


@activity.defn
async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Use Docling to extract plain text from PDF bytes."""
    from docling.document_converter import DocumentConverter

    log.info("extract_text.start", size_bytes=len(pdf_bytes))

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    try:
        converter = DocumentConverter()
        result = converter.convert(str(tmp_path))
        text = result.document.export_to_markdown()
    finally:
        tmp_path.unlink(missing_ok=True)

    log.info("extract_text.done", chars=len(text))
    return text
