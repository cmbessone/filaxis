import hashlib
from dataclasses import dataclass
from pathlib import Path

import boto3
from temporalio import activity

from filaxis.config import settings
from filaxis.logging import get_logger

log = get_logger(__name__)


@dataclass
class DownloadResult:
    pdf_bytes: bytes
    pdf_hash: str  # SHA-256 hex


@activity.defn
async def download_pdf(s3_key: str) -> DownloadResult:
    """Download PDF from S3 (or local path in dev) and return bytes + SHA-256 hash."""
    log.info("download_pdf.start", s3_key=s3_key)

    # Local file shortcut for dev/test (s3_key starts with "/")
    if s3_key.startswith("/") or Path(s3_key).exists():
        pdf_bytes = Path(s3_key).read_bytes()
    else:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        response = s3.get_object(Bucket=settings.s3_bucket, Key=s3_key)
        pdf_bytes = response["Body"].read()

    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    log.info("download_pdf.done", s3_key=s3_key, pdf_hash=pdf_hash, size_bytes=len(pdf_bytes))
    return DownloadResult(pdf_bytes=pdf_bytes, pdf_hash=pdf_hash)
