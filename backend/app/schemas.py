from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


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
    source_name: str = Field(min_length=1, max_length=160)
    activity_category: str = Field(default="General", min_length=1, max_length=160)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    location: str | None = Field(default="Central Steel Plant", max_length=160)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("activity_date")
    @classmethod
    def activity_date_cannot_be_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Activity date cannot be in the future")
        return value

    @field_validator("source_name", "activity_category", "unit", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


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
    reason: str = Field(min_length=8, max_length=2000)
    changed_by: str = Field(default="admin@demo.com", min_length=3, max_length=120)

    @field_validator("reason", "changed_by", mode="before")
    @classmethod
    def strip_override_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


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
    metric_name: str = Field(default="Tons of Steel Produced", min_length=1, max_length=160)
    value: float = Field(gt=0)
    unit: str = Field(default="tonnes", min_length=1, max_length=80)

    @field_validator("metric_date")
    @classmethod
    def metric_date_cannot_be_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Metric date cannot be in the future")
        return value

    @field_validator("metric_name", "unit", mode="before")
    @classmethod
    def strip_metric_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class BusinessMetricRead(BaseModel):
    id: int
    metric_date: date
    metric_name: str
    value: float
    unit: str

    model_config = {"from_attributes": True}
