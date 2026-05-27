"""LOINC codes for the CBC (Complete Blood Count) panel."""

CBC_PANEL = "58410-2"

LOINC_CODES: dict[str, dict] = {
    "hemoglobin": {
        "code": "718-7",
        "display": "Hemoglobin [Mass/volume] in Blood",
        "unit": "g/dL",
    },
    "hematocrit": {
        "code": "4544-3",
        "display": "Hematocrit [Volume Fraction] of Blood",
        "unit": "%",
    },
    "rbc": {
        "code": "789-8",
        "display": "Erythrocytes [#/volume] in Blood",
        "unit": "/mm3",
    },
    "mcv": {
        "code": "787-2",
        "display": "MCV [Entitic volume]",
        "unit": "fL",
    },
    "mch": {
        "code": "785-6",
        "display": "MCH [Entitic mass]",
        "unit": "pg",
    },
    "mchc": {
        "code": "786-4",
        "display": "MCHC [Mass/volume]",
        "unit": "%",
    },
    "rdw": {
        "code": "788-0",
        "display": "Erythrocyte distribution width [Ratio]",
        "unit": "%",
    },
    "wbc": {
        "code": "6690-2",
        "display": "Leukocytes [#/volume] in Blood",
        "unit": "/mm3",
    },
    "neutrophils_pct": {
        "code": "770-4",
        "display": "Neutrophils/100 leukocytes in Blood",
        "unit": "%",
    },
    "lymphocytes_pct": {
        "code": "736-5",
        "display": "Lymphocytes/100 leukocytes in Blood",
        "unit": "%",
    },
    "monocytes_pct": {
        "code": "5905-5",
        "display": "Monocytes/100 leukocytes in Blood",
        "unit": "%",
    },
    "eosinophils_pct": {
        "code": "713-8",
        "display": "Eosinophils/100 leukocytes in Blood",
        "unit": "%",
    },
    "basophils_pct": {
        "code": "706-2",
        "display": "Basophils/100 leukocytes in Blood",
        "unit": "%",
    },
    "platelets": {
        "code": "777-3",
        "display": "Platelets [#/volume] in Blood",
        "unit": "/mm3",
    },
}

VALID_LOINC_CODES = {v["code"] for v in LOINC_CODES.values()} | {CBC_PANEL}
