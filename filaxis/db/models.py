import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filaxis_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reports: Mapped[list["DiagnosticReport"]] = relationship("DiagnosticReport", back_populates="patient")


class DiagnosticReport(Base):
    __tablename__ = "diagnostic_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), nullable=False)
    pdf_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    report_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    wbc_count: Mapped[float | None] = mapped_column(Float, nullable=True)
    fhir_resource: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="final")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    patient: Mapped["Patient"] = relationship("Patient", back_populates="reports")

    __table_args__ = (
        Index("idx_dr_patient_date", "patient_id", "report_date"),
        Index("idx_dr_wbc", "wbc_count"),
        Index("idx_dr_pdf_hash", "pdf_hash"),
    )
