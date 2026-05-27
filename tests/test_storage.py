"""Unit tests for the storage activity (DB upsert + cache check)."""

import json
import pytest

from filaxis.activities.conversion import ConversionResult
from filaxis.activities.storage import check_cache, store_report, CacheCheckResult
from filaxis.fhir.loinc import CBC_PANEL

SAMPLE_FHIR = {
    "resourceType": "DiagnosticReport",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": CBC_PANEL}]},
    "subject": {"reference": "Patient/PAT-00123"},
    "result": [],
    "patient_filaxis_id": "PAT-00123",
    "patient_name": "Ana García",
}


@pytest.fixture
def sample_conversion() -> ConversionResult:
    return ConversionResult(
        fhir_dict=SAMPLE_FHIR,
        patient_filaxis_id="PAT-00123",
        patient_name="Ana García",
        wbc_count=4950.0,
    )


@pytest.mark.asyncio
async def test_cache_miss_on_new_hash(sample_conversion):
    result = await check_cache("deadbeef" * 8)
    assert result == CacheCheckResult(cached=False)


@pytest.mark.asyncio
async def test_store_then_cache_hit(sample_conversion):
    pdf_hash = "abc123" * 10 + "abcd"  # 64 hex chars
    pdf_hash = pdf_hash[:64]
    report_id = await store_report(sample_conversion, pdf_hash, s3_key="test.pdf")
    assert report_id is not None

    cache = await check_cache(pdf_hash)
    assert cache.cached is True
    assert cache.report_id == report_id


@pytest.mark.asyncio
async def test_store_upserts_patient(sample_conversion):
    """Calling store_report twice for different PDFs of the same patient creates only one Patient row."""
    pdf_hash_1 = "a" * 64
    pdf_hash_2 = "b" * 64

    await store_report(sample_conversion, pdf_hash_1, s3_key="file1.pdf")
    await store_report(sample_conversion, pdf_hash_2, s3_key="file2.pdf")

    from filaxis.db.engine import AsyncSessionLocal
    from filaxis.db.models import Patient
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as session:
        count = (await session.execute(
            select(func.count()).select_from(Patient).where(Patient.filaxis_id == "PAT-00123")
        )).scalar_one()

    assert count == 1


@pytest.mark.asyncio
async def test_store_overwrites_on_duplicate_hash(sample_conversion):
    """Storing the same pdf_hash twice updates the existing row, not creates a duplicate."""
    pdf_hash = "c" * 64
    id1 = await store_report(sample_conversion, pdf_hash, s3_key="file.pdf")

    updated = ConversionResult(
        fhir_dict={**SAMPLE_FHIR},
        patient_filaxis_id="PAT-00123",
        patient_name="Ana García Updated",
        wbc_count=3800.0,
    )
    id2 = await store_report(updated, pdf_hash, s3_key="file.pdf")

    assert id1 == id2

    from filaxis.db.engine import AsyncSessionLocal
    from filaxis.db.models import DiagnosticReport
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        report = (await session.execute(
            select(DiagnosticReport).where(DiagnosticReport.pdf_hash == pdf_hash)
        )).scalar_one()

    assert report.wbc_count == 3800.0
