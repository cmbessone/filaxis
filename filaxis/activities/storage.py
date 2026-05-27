import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from temporalio import activity

from filaxis.activities.conversion import ConversionResult
from filaxis.db.engine import AsyncSessionLocal
from filaxis.db.models import DiagnosticReport, Patient
from filaxis.logging import get_logger

log = get_logger(__name__)


@dataclass
class CacheCheckResult:
    cached: bool
    report_id: str | None = None


@activity.defn
async def check_cache(pdf_hash: str) -> CacheCheckResult:
    """Return cached report_id if PDF was already processed, else cached=False."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DiagnosticReport).where(DiagnosticReport.pdf_hash == pdf_hash)
        )
        report = result.scalar_one_or_none()
        if report:
            log.info("check_cache.hit", pdf_hash=pdf_hash, report_id=report.id)
            return CacheCheckResult(cached=True, report_id=report.id)
        return CacheCheckResult(cached=False)


@activity.defn
async def store_report(
    conversion: ConversionResult,
    pdf_hash: str,
    s3_key: str | None,
) -> str:
    """Upsert Patient + DiagnosticReport; returns the report_id."""
    async with AsyncSessionLocal() as session:
        # Upsert patient
        result = await session.execute(
            select(Patient).where(Patient.filaxis_id == conversion.patient_filaxis_id)
        )
        patient = result.scalar_one_or_none()
        if not patient:
            patient = Patient(
                id=str(uuid.uuid4()),
                filaxis_id=conversion.patient_filaxis_id,
                name=conversion.patient_name,
            )
            session.add(patient)
            await session.flush()
        else:
            patient.name = conversion.patient_name

        # Parse report date from FHIR resource
        report_date_str = conversion.fhir_dict.get("effectiveDateTime")
        report_date: datetime | None = None
        if report_date_str:
            try:
                report_date = datetime.fromisoformat(report_date_str)
            except ValueError:
                log.warning("store_report.invalid_date", value=report_date_str)

        # Upsert report (keyed on pdf_hash)
        result = await session.execute(
            select(DiagnosticReport).where(DiagnosticReport.pdf_hash == pdf_hash)
        )
        report = result.scalar_one_or_none()
        if not report:
            report = DiagnosticReport(
                id=str(uuid.uuid4()),
                patient_id=patient.id,
                pdf_hash=pdf_hash,
            )
            session.add(report)

        report.s3_key = s3_key
        report.report_date = report_date
        report.wbc_count = conversion.wbc_count
        report.fhir_resource = json.dumps(conversion.fhir_dict)
        report.status = "final"

        await session.commit()

        log.info("store_report.done", report_id=report.id, patient_id=patient.id, wbc_count=conversion.wbc_count)
        return report.id
