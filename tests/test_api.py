"""Integration tests for FastAPI endpoints (Uses Case A & B)."""

import json
import uuid
import pytest
from datetime import datetime

from tests.conftest import make_patient_token, make_physician_token
from filaxis.fhir.loinc import CBC_PANEL

SAMPLE_FHIR = json.dumps({
    "resourceType": "DiagnosticReport",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": CBC_PANEL}]},
    "subject": {"reference": "Patient/PAT-001"},
    "result": [],
    "patient_filaxis_id": "PAT-001",
    "patient_name": "Test Patient",
})


async def _seed_report(filaxis_id: str, name: str, wbc: float, report_date: datetime):
    from filaxis.db.engine import AsyncSessionLocal
    from filaxis.db.models import Patient, DiagnosticReport

    async with AsyncSessionLocal() as session:
        patient = Patient(id=str(uuid.uuid4()), filaxis_id=filaxis_id, name=name)
        session.add(patient)
        await session.flush()

        report = DiagnosticReport(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            pdf_hash=uuid.uuid4().hex,
            wbc_count=wbc,
            report_date=report_date,
            fhir_resource=SAMPLE_FHIR,
        )
        session.add(report)
        await session.commit()
        return patient.id


# ── Use Case A ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_reports_own_token(api_client):
    await _seed_report("PAT-001", "Test Patient", 4950.0, datetime(2024, 1, 10))
    token = make_patient_token("PAT-001")
    response = api_client.get("/patients/PAT-001/reports", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["wbc_count"] == 4950.0


@pytest.mark.asyncio
async def test_patient_reports_physician_can_access(api_client):
    await _seed_report("PAT-002", "Another Patient", 5000.0, datetime(2024, 2, 1))
    token = make_physician_token()
    response = api_client.get("/patients/PAT-002/reports", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_patient_reports_other_patient_denied(api_client):
    await _seed_report("PAT-003", "Third Patient", 5000.0, datetime(2024, 3, 1))
    token = make_patient_token("PAT-OTHER")
    response = api_client.get("/patients/PAT-003/reports", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_patient_reports_pagination(api_client):
    pid = "PAT-004"
    for i, month in enumerate([1, 2, 3], start=1):
        await _seed_report(pid, "Paginated Patient", 4800.0 + i * 10, datetime(2024, month, 1))
    token = make_patient_token(pid)
    resp = api_client.get(
        f"/patients/{pid}/reports?page=1&page_size=2&order=desc",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_patient_reports_no_auth(api_client):
    response = api_client.get("/patients/PAT-001/reports")
    assert response.status_code == 403


# ── Use Case B ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_low_wbc_patients_physician_only(api_client):
    await _seed_report("PAT-L1", "Low WBC Patient", 3200.0, datetime(2024, 1, 1))
    token = make_physician_token()
    response = api_client.get("/physician/low-wbc-patients", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    patients = response.json()
    filaxis_ids = [p["patient_id"] for p in patients]
    assert "PAT-L1" in filaxis_ids


@pytest.mark.asyncio
async def test_low_wbc_excludes_normal_wbc(api_client):
    await _seed_report("PAT-N1", "Normal WBC", 6000.0, datetime(2024, 1, 1))
    await _seed_report("PAT-L2", "Low WBC", 4000.0, datetime(2024, 1, 1))
    token = make_physician_token()
    response = api_client.get("/physician/low-wbc-patients", headers={"Authorization": f"Bearer {token}"})
    ids = [p["patient_id"] for p in response.json()]
    assert "PAT-N1" not in ids
    assert "PAT-L2" in ids


@pytest.mark.asyncio
async def test_low_wbc_patient_token_denied(api_client):
    token = make_patient_token("PAT-001")
    response = api_client.get("/physician/low-wbc-patients", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_health_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
