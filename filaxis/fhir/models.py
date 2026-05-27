"""Minimal FHIR R5 Pydantic models for CBC DiagnosticReport."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, field_validator
from filaxis.fhir.loinc import VALID_LOINC_CODES


class Coding(BaseModel):
    system: str
    code: str
    display: str | None = None


class CodeableConcept(BaseModel):
    coding: list[Coding]
    text: str | None = None


class Reference(BaseModel):
    reference: str
    display: str | None = None


class ValueQuantity(BaseModel):
    value: float
    unit: str
    system: str = "http://unitsofmeasure.org"


class Observation(BaseModel):
    resourceType: Literal["Observation"] = "Observation"
    status: Literal["final", "preliminary"] = "final"
    code: CodeableConcept
    subject: Reference
    valueQuantity: ValueQuantity
    effectiveDateTime: datetime | None = None

    @field_validator("code")
    @classmethod
    def validate_loinc(cls, v: CodeableConcept) -> CodeableConcept:
        codes = {c.code for c in v.coding}
        if not codes.intersection(VALID_LOINC_CODES):
            raise ValueError(f"No valid CBC LOINC code found in: {codes}")
        return v


class DiagnosticReport(BaseModel):
    resourceType: Literal["DiagnosticReport"] = "DiagnosticReport"
    status: Literal["final", "preliminary", "registered"] = "final"
    code: CodeableConcept
    subject: Reference
    effectiveDateTime: datetime | None = None
    result: list[Observation] = []

    # Extension fields (not standard FHIR, used for pipeline metadata)
    patient_filaxis_id: str = ""
    patient_name: str = ""
