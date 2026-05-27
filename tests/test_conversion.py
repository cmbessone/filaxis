"""Unit tests for the LLM conversion activity."""

import json
import pytest

from tests.conftest import SAMPLE_EXTRACTED_TEXT, MOCK_LLM_JSON


@pytest.mark.asyncio
async def test_convert_to_fhir_produces_diagnostic_report(mock_anthropic_response):
    from filaxis.activities.conversion import convert_to_fhir

    result = await convert_to_fhir(SAMPLE_EXTRACTED_TEXT)

    assert result.patient_filaxis_id == "PAT-00123"
    assert result.patient_name == "Ana García"
    assert result.wbc_count == 4950.0
    assert result.fhir_dict["resourceType"] == "DiagnosticReport"
    assert result.fhir_dict["status"] == "final"


@pytest.mark.asyncio
async def test_convert_fhir_observations_have_loinc_codes(mock_anthropic_response):
    from filaxis.activities.conversion import convert_to_fhir
    from filaxis.fhir.loinc import VALID_LOINC_CODES

    result = await convert_to_fhir(SAMPLE_EXTRACTED_TEXT)
    observations = result.fhir_dict["result"]

    assert len(observations) == len(MOCK_LLM_JSON["observations"])
    for obs in observations:
        codes = {c["code"] for c in obs["code"]["coding"]}
        assert codes & VALID_LOINC_CODES, f"No valid LOINC code in {codes}"


@pytest.mark.asyncio
async def test_convert_fhir_wbc_extracted_correctly(mock_anthropic_response):
    from filaxis.activities.conversion import convert_to_fhir

    result = await convert_to_fhir(SAMPLE_EXTRACTED_TEXT)
    assert result.wbc_count == 4950.0


@pytest.mark.asyncio
async def test_convert_fhir_unknown_loinc_key_skipped(mock_anthropic_response):
    """Observations with unknown loinc_key are silently skipped (logged as warning)."""
    import json
    from unittest.mock import AsyncMock, patch

    bad_json = {**MOCK_LLM_JSON, "observations": [{"loinc_key": "UNKNOWN", "value": 99, "unit": "?"}]}
    mock_msg = AsyncMock()
    mock_msg.content = [AsyncMock(text=json.dumps(bad_json))]
    mock_msg.usage = AsyncMock(output_tokens=10)
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    with patch("filaxis.activities.conversion.anthropic.AsyncAnthropic", return_value=mock_client):
        from filaxis.activities.conversion import convert_to_fhir
        result = await convert_to_fhir(SAMPLE_EXTRACTED_TEXT)

    assert result.fhir_dict["result"] == []
