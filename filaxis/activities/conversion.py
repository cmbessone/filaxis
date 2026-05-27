import json
from dataclasses import dataclass

import anthropic
from temporalio import activity

from filaxis.config import settings
from filaxis.fhir.loinc import LOINC_CODES, CBC_PANEL
from filaxis.logging import get_logger

log = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a medical data extraction assistant. Extract all CBC (Complete Blood Count) values from
the lab report text and return a single JSON object matching the schema below. Be precise with
numeric values — copy them exactly as they appear in the text.

Schema:
{
  "patient_filaxis_id": "<string — the unique Filaxis patient ID found in the report, or 'unknown'>",
  "patient_name": "<string — full patient name from the report, or 'unknown'>",
  "report_date": "<ISO 8601 date string, or null if not found>",
  "observations": [
    {
      "loinc_key": "<one of: hemoglobin, hematocrit, rbc, mcv, mch, mchc, rdw, wbc,
                      neutrophils_pct, lymphocytes_pct, monocytes_pct,
                      eosinophils_pct, basophils_pct, platelets>",
      "value": <number>,
      "unit": "<unit string from the report>"
    }
  ]
}

Return ONLY valid JSON. No markdown fences, no explanation.
"""


@dataclass
class ConversionResult:
    fhir_dict: dict
    patient_filaxis_id: str
    patient_name: str
    wbc_count: float | None


@activity.defn
async def convert_to_fhir(extracted_text: str) -> ConversionResult:
    """Call the LLM to map extracted CBC text to a FHIR R5 DiagnosticReport dict."""
    log.info("convert_to_fhir.start", text_chars=len(extracted_text))

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": extracted_text}],
    )

    raw_json = message.content[0].text.strip()
    log.info("convert_to_fhir.llm_response", tokens_used=message.usage.output_tokens)

    parsed = json.loads(raw_json)
    fhir_dict = _build_fhir_resource(parsed)

    wbc_count = next(
        (obs["value"] for obs in parsed.get("observations", []) if obs["loinc_key"] == "wbc"),
        None,
    )

    log.info("convert_to_fhir.done", patient_id=parsed.get("patient_filaxis_id"), wbc_count=wbc_count)
    return ConversionResult(
        fhir_dict=fhir_dict,
        patient_filaxis_id=parsed.get("patient_filaxis_id", "unknown"),
        patient_name=parsed.get("patient_name", "unknown"),
        wbc_count=float(wbc_count) if wbc_count is not None else None,
    )


def _build_fhir_resource(parsed: dict) -> dict:
    patient_ref = f"Patient/{parsed.get('patient_filaxis_id', 'unknown')}"
    report_date = parsed.get("report_date")

    observations = []
    for obs in parsed.get("observations", []):
        key = obs.get("loinc_key")
        loinc = LOINC_CODES.get(key)
        if not loinc:
            log.warning("convert_to_fhir.unknown_loinc_key", key=key)
            continue

        observations.append({
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{"system": "http://loinc.org", "code": loinc["code"], "display": loinc["display"]}],
                "text": loinc["display"],
            },
            "subject": {"reference": patient_ref},
            "valueQuantity": {
                "value": obs["value"],
                "unit": obs.get("unit", loinc["unit"]),
                "system": "http://unitsofmeasure.org",
            },
            **({"effectiveDateTime": report_date} if report_date else {}),
        })

    return {
        "resourceType": "DiagnosticReport",
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": CBC_PANEL, "display": "CBC panel"}],
            "text": "Complete Blood Count",
        },
        "subject": {"reference": patient_ref, "display": parsed.get("patient_name", "")},
        **({"effectiveDateTime": report_date} if report_date else {}),
        "result": observations,
        "patient_filaxis_id": parsed.get("patient_filaxis_id", "unknown"),
        "patient_name": parsed.get("patient_name", "unknown"),
    }
