import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from filaxis.api.routes import ingest, patient, physician
from filaxis.config import settings
from filaxis.db.engine import init_db
from filaxis.logging import configure_logging

configure_logging()

app = FastAPI(
    title="FILAXIS PDF Pipeline API",
    description=(
        "CBC lab PDFs → FHIR R5 via Temporal + Docling + Claude.\n\n"
        "**Quick start for Swagger testing:**\n"
        "1. Call `POST /dev/seed` — populates DB with sample patients and returns JWTs.\n"
        "2. Copy the `patient_token` or `physician_token` from the response.\n"
        "3. Click **Authorize** (top right) and paste `Bearer <token>`.\n"
        "4. Try `GET /patients/PAT-001/reports` or `GET /physician/low-wbc-patients`."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, tags=["ingest"])
app.include_router(patient.router, tags=["patient"])
app.include_router(physician.router, tags=["physician"])

if settings.environment != "production":
    from filaxis.api.routes import dev
    app.include_router(dev.router)


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


def main() -> None:
    uvicorn.run("filaxis.api.app:app", host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
