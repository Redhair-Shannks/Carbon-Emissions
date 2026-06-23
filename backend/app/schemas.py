from datetime import date, datetime

from pydantic import BaseModel, Field


class EmissionFactorRead(BaseModel):
    id: int
    scope: str
    source_name: str
    activity_category: str
    unit: str
    factor_kgco2e_per_unit: float
    factor_unit: str
    source: str
    version: str
    valid_from: date
    valid_to: date | None

    model_config = {"from_attributes": True}


class EmissionRecordCreate(BaseModel):
    activity_date: date
    source_name: str
    activity_category: str = "General"
    quantity: float = Field(gt=0)
    unit: str
    location: str | None = "Central Steel Plant"
    notes: str | None = None


class EmissionRecordRead(BaseModel):
    id: int
    scope: str
    activity_date: date
    source_name: str
    activity_category: str
    quantity: float
    unit: str
    factor_id: int
    calculated_emissions_kgco2e: float
    final_emissions_kgco2e: float
    is_overridden: bool
    location: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OverrideCreate(BaseModel):
    new_emissions_kgco2e: float = Field(ge=0)
    reason: str = Field(min_length=8)
    changed_by: str = "admin@demo.com"


class AuditLogRead(BaseModel):
    id: int
    record_id: int
    field_name: str
    old_value: float
    new_value: float
    reason: str
    changed_by: str
    changed_at: datetime

    model_config = {"from_attributes": True}


class BusinessMetricCreate(BaseModel):
    metric_date: date
    metric_name: str = "Tons of Steel Produced"
    value: float = Field(gt=0)
    unit: str = "tonnes"


class BusinessMetricRead(BaseModel):
    id: int
    metric_date: date
    metric_name: str
    value: float
    unit: str

    model_config = {"from_attributes": True}
