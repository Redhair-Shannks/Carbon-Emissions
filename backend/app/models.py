from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmissionFactor(Base):
    __tablename__ = "emission_factors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    scope: Mapped[str] = mapped_column(String(16), index=True)
    source_name: Mapped[str] = mapped_column(String(160), index=True)
    activity_category: Mapped[str] = mapped_column(String(160), index=True)
    unit: Mapped[str] = mapped_column(String(40))
    factor_kgco2e_per_unit: Mapped[float] = mapped_column(Float)
    factor_unit: Mapped[str] = mapped_column(String(80), default="kgCO2e/unit")
    source: Mapped[str] = mapped_column(String(240))
    version: Mapped[str] = mapped_column(String(40))
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    records: Mapped[list["EmissionRecord"]] = relationship(back_populates="factor")


class EmissionRecord(Base):
    __tablename__ = "emission_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    scope: Mapped[str] = mapped_column(String(16), index=True)
    activity_date: Mapped[date] = mapped_column(Date, index=True)
    source_name: Mapped[str] = mapped_column(String(160), index=True)
    activity_category: Mapped[str] = mapped_column(String(160), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    factor_id: Mapped[int] = mapped_column(ForeignKey("emission_factors.id"))
    calculated_emissions_kgco2e: Mapped[float] = mapped_column(Float)
    final_emissions_kgco2e: Mapped[float] = mapped_column(Float)
    is_overridden: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    factor: Mapped[EmissionFactor] = relationship(back_populates="records")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("emission_records.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(80), default="final_emissions_kgco2e")
    old_value: Mapped[float] = mapped_column(Float)
    new_value: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(String(120), default="admin@demo.com")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    record: Mapped[EmissionRecord] = relationship(back_populates="audit_logs")


class BusinessMetric(Base):
    __tablename__ = "business_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    metric_date: Mapped[date] = mapped_column(Date, index=True)
    metric_name: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index(
    "ix_factor_lookup",
    EmissionFactor.scope,
    EmissionFactor.source_name,
    EmissionFactor.unit,
    EmissionFactor.valid_from,
    EmissionFactor.valid_to,
)
Index("ix_record_analytics", EmissionRecord.scope, EmissionRecord.activity_date, EmissionRecord.source_name)
