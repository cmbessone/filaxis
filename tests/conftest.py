import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from filaxis.config import settings
from filaxis.db.engine import AsyncSessionLocal
from filaxis.db.models import Base

# ── In-memory test DB ──────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_test_engine = create_async_engine(TEST_DB_URL)
_TestSession = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Patch the global session factory used by activities and routes
    with patch("filaxis.activities.storage.AsyncSessionLocal", _TestSession), \
         patch("filaxis.db.engine.AsyncSessionLocal", _TestSession), \
         patch("filaxis.api.routes.patient.AsyncSessionLocal", _TestSession), \
         patch("filaxis.api.routes.physician.AsyncSessionLocal", _TestSession):
        yield

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Sample PDF fixture ─────────────────────────────────────────────────────────

SAMPLE_PDF_PATH = Path(__file__).parent.parent / "hemogramas-001" / "hemograma_ficticio_1.pdf"


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    return SAMPLE_PDF_PATH.read_bytes()


@pytest.fixture
def sample_pdf_hash(sample_pdf_bytes: bytes) -> str:
    import hashlib
    return hashlib.sha256(sample_pdf_bytes).hexdigest()


# ── Extracted text fixture (avoids running Docling in unit tests) ──────────────

SAMPLE_EXTRACTED_TEXT = """
HEMOGRAMA COMPLETO – Informe Ficticio 1
Patient Name: Ana García
Patient ID: PAT-00123

HEMATÍES / ERITROCITOS
Hematocrito: 41 %
Hemoglobina: 13.7 g/dL
Glóbulos rojos: 4620000 /mm³

ÍNDICES HEMATIMÉTRICOS
VCM: 87 fL
HCM: 28.4 pg
CHCM: 33.2 %
RDW: 12.3 %

LEUCOCITOS
Glóbulos blancos: 4950 /mm³
Neutrófilos: 56 %
Linfocitos: 32 %
Monocitos: 6 %
Eosinófilos: 3 %
Basófilos: 1 %

PLAQUETAS
Recuento plaquetario: 248000 /mm³
"""


# ── Mock LLM response ──────────────────────────────────────────────────────────

MOCK_LLM_JSON = {
    "patient_filaxis_id": "PAT-00123",
    "patient_name": "Ana García",
    "report_date": "2024-03-15T00:00:00",
    "observations": [
        {"loinc_key": "hematocrit", "value": 41.0, "unit": "%"},
        {"loinc_key": "hemoglobin", "value": 13.7, "unit": "g/dL"},
        {"loinc_key": "rbc", "value": 4620000.0, "unit": "/mm3"},
        {"loinc_key": "mcv", "value": 87.0, "unit": "fL"},
        {"loinc_key": "mch", "value": 28.4, "unit": "pg"},
        {"loinc_key": "mchc", "value": 33.2, "unit": "%"},
        {"loinc_key": "rdw", "value": 12.3, "unit": "%"},
        {"loinc_key": "wbc", "value": 4950.0, "unit": "/mm3"},
        {"loinc_key": "neutrophils_pct", "value": 56.0, "unit": "%"},
        {"loinc_key": "lymphocytes_pct", "value": 32.0, "unit": "%"},
        {"loinc_key": "monocytes_pct", "value": 6.0, "unit": "%"},
        {"loinc_key": "eosinophils_pct", "value": 3.0, "unit": "%"},
        {"loinc_key": "basophils_pct", "value": 1.0, "unit": "%"},
        {"loinc_key": "platelets", "value": 248000.0, "unit": "/mm3"},
    ],
}


@pytest.fixture
def mock_anthropic_response():
    """Patch Anthropic client to return deterministic CBC JSON."""
    mock_msg = AsyncMock()
    mock_msg.content = [AsyncMock(text=json.dumps(MOCK_LLM_JSON))]
    mock_msg.usage = AsyncMock(output_tokens=400)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("filaxis.activities.conversion.anthropic.AsyncAnthropic", return_value=mock_client):
        yield mock_client


# ── JWT helpers ────────────────────────────────────────────────────────────────

def make_patient_token(patient_id: str) -> str:
    return jwt.encode(
        {"sub": patient_id, "role": "patient"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def make_physician_token() -> str:
    return jwt.encode(
        {"sub": "dr-house", "role": "physician"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


# ── FastAPI test client ────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    from filaxis.api.app import app
    with TestClient(app) as client:
        yield client
