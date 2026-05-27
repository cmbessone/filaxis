"""Dev-only endpoints for seeding test data and generating JWTs.

Only mounted when ENVIRONMENT != production.
"""

import json
import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from filaxis.api.auth import TokenPayload
from filaxis.config import settings
from filaxis.db.engine import AsyncSessionLocal
from filaxis.db.models import DiagnosticReport, Patient
from filaxis.fhir.loinc import CBC_PANEL
from jose import jwt

router = APIRouter(prefix="/dev", tags=["dev (seed & tokens)"])


class SeedResponse(BaseModel):
    message: str
    patient_token: str
    physician_token: str
    patient_ids: list[str]


def _make_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _fhir(patient_filaxis_id: str, wbc: float) -> str:
    return json.dumps({
        "resourceType": "DiagnosticReport",
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": CBC_PANEL, "display": "CBC panel"}],
            "text": "Complete Blood Count",
        },
        "subject": {
            "reference": f"Patient/{patient_filaxis_id}",
        },
        "result": [
            {
                "resourceType": "Observation",
                "status": "final",
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "6690-2", "display": "Leukocytes [#/volume] in Blood"}]
                },
                "subject": {"reference": f"Patient/{patient_filaxis_id}"},
                "valueQuantity": {"value": wbc, "unit": "/mm3", "system": "http://unitsofmeasure.org"},
            },
            {
                "resourceType": "Observation",
                "status": "final",
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "718-7", "display": "Hemoglobin [Mass/volume] in Blood"}]
                },
                "subject": {"reference": f"Patient/{patient_filaxis_id}"},
                "valueQuantity": {"value": 13.7, "unit": "g/dL", "system": "http://unitsofmeasure.org"},
            },
        ],
        "patient_filaxis_id": patient_filaxis_id,
        "patient_name": "",
    })


_SEED_DATA = [
    ("PAT-001", "Ana García",    4950.0, datetime(2024, 1, 10)),
    ("PAT-001", "Ana García",    5100.0, datetime(2024, 7, 15)),
    ("PAT-002", "Bruno López",   3800.0, datetime(2024, 3, 5)),   # WBC < 4500
    ("PAT-003", "Carla Méndez",  4200.0, datetime(2024, 2, 20)),  # WBC < 4500
    ("PAT-004", "Diego Romero",  6200.0, datetime(2024, 4, 1)),
]


@router.post("/seed", response_model=SeedResponse)
async def seed() -> SeedResponse:
    """Populate DB with sample patients and reports. Safe to call multiple times (upserts)."""
    async with AsyncSessionLocal() as session:
        seen_patients: dict[str, str] = {}

        for filaxis_id, name, wbc, report_date in _SEED_DATA:
            # Upsert patient
            from sqlalchemy import select
            result = await session.execute(select(Patient).where(Patient.filaxis_id == filaxis_id))
            patient = result.scalar_one_or_none()
            if not patient:
                patient = Patient(id=str(uuid.uuid4()), filaxis_id=filaxis_id, name=name)
                session.add(patient)
                await session.flush()
            seen_patients[filaxis_id] = patient.id

            # Insert report (skip if hash already exists)
            pdf_hash = f"seed-{filaxis_id}-{report_date.date()}".ljust(64, "0")[:64]
            res2 = await session.execute(
                select(DiagnosticReport).where(DiagnosticReport.pdf_hash == pdf_hash)
            )
            if not res2.scalar_one_or_none():
                report = DiagnosticReport(
                    id=str(uuid.uuid4()),
                    patient_id=patient.id,
                    pdf_hash=pdf_hash,
                    report_date=report_date,
                    wbc_count=wbc,
                    fhir_resource=_fhir(filaxis_id, wbc),
                )
                session.add(report)

        await session.commit()

    return SeedResponse(
        message="Seeded 4 patients, 5 reports. PAT-002 and PAT-003 have WBC < 4500.",
        patient_token=_make_token("PAT-001", "patient"),
        physician_token=_make_token("dr-house", "physician"),
        patient_ids=list(seen_patients.keys()),
    )


@router.post("/token", response_model=dict)
async def generate_token(sub: str, role: str = "patient") -> dict:
    """Generate a JWT for any subject/role. Use for manual Swagger testing."""
    token = _make_token(sub, role)
    return {"token": token, "bearer": f"Bearer {token}"}
