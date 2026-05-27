import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from filaxis.api.routes import ingest, patient, physician
from filaxis.db.engine import init_db
from filaxis.logging import configure_logging

configure_logging()

app = FastAPI(
    title="FILAXIS PDF Pipeline API",
    description="Ingest CBC lab PDFs from S3 and expose FHIR R5 results.",
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


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def main() -> None:
    uvicorn.run("filaxis.api.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
