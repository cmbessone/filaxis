import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from filaxis.api.auth import TokenPayload, get_current_token
from filaxis.db.engine import AsyncSessionLocal
from filaxis.db.models import DiagnosticReport, Patient
from filaxis.logging import get_logger

router = APIRouter()
log = get_logger(__name__)


class ReportItem(BaseModel):
    report_id: str
    report_date: str | None
    wbc_count: float | None
    fhir_resource: dict


class PatientReportsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ReportItem]


@router.get("/patients/{patient_id}/reports", response_model=PatientReportsResponse)
async def get_patient_reports(
    patient_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    order: Literal["asc", "desc"] = Query(default="desc"),
    token: TokenPayload = Depends(get_current_token),
) -> PatientReportsResponse:
    """Return paginated CBC reports for a patient. Requires patient's own token or physician."""
    if token.role != "physician" and token.sub != patient_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    async with AsyncSessionLocal() as session:
        patient_result = await session.execute(
            select(Patient).where(Patient.filaxis_id == patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        sort_col = DiagnosticReport.report_date.asc() if order == "asc" else DiagnosticReport.report_date.desc()

        count_result = await session.execute(
            select(func.count()).select_from(DiagnosticReport).where(DiagnosticReport.patient_id == patient.id)
        )
        total = count_result.scalar_one()

        reports_result = await session.execute(
            select(DiagnosticReport)
            .where(DiagnosticReport.patient_id == patient.id)
            .order_by(sort_col)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        reports = reports_result.scalars().all()

    log.info("get_patient_reports", patient_id=patient_id, total=total, page=page)
    return PatientReportsResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            ReportItem(
                report_id=r.id,
                report_date=r.report_date.isoformat() if r.report_date else None,
                wbc_count=r.wbc_count,
                fhir_resource=json.loads(r.fhir_resource),
            )
            for r in reports
        ],
    )
