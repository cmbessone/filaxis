from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from filaxis.api.auth import TokenPayload, require_physician
from filaxis.db.engine import AsyncSessionLocal
from filaxis.db.models import DiagnosticReport, Patient
from filaxis.logging import get_logger

router = APIRouter()
log = get_logger(__name__)

_WBC_THRESHOLD = 4500.0


class LowWBCPatient(BaseModel):
    patient_id: str
    patient_name: str
    wbc_count: float
    report_date: str | None


@router.get("/physician/low-wbc-patients", response_model=list[LowWBCPatient])
async def get_low_wbc_patients(
    _token: TokenPayload = Depends(require_physician),
) -> list[LowWBCPatient]:
    """Return patients whose most recent CBC shows WBC < 4500 /mm³."""
    async with AsyncSessionLocal() as session:
        # Subquery: max report_date per patient (most recent)
        from sqlalchemy import func

        latest_subq = (
            select(
                DiagnosticReport.patient_id,
                func.max(DiagnosticReport.report_date).label("latest_date"),
            )
            .group_by(DiagnosticReport.patient_id)
            .subquery()
        )

        result = await session.execute(
            select(DiagnosticReport, Patient)
            .join(Patient, Patient.id == DiagnosticReport.patient_id)
            .join(
                latest_subq,
                (DiagnosticReport.patient_id == latest_subq.c.patient_id)
                & (DiagnosticReport.report_date == latest_subq.c.latest_date),
            )
            .where(DiagnosticReport.wbc_count < _WBC_THRESHOLD)
            .order_by(DiagnosticReport.wbc_count.asc())
        )
        rows = result.all()

    log.info("get_low_wbc_patients", count=len(rows))
    return [
        LowWBCPatient(
            patient_id=patient.filaxis_id,
            patient_name=patient.name,
            wbc_count=report.wbc_count,
            report_date=report.report_date.isoformat() if report.report_date else None,
        )
        for report, patient in rows
    ]
