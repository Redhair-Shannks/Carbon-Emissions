from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db, init_db
from app.models import AuditLog, BusinessMetric, EmissionFactor, EmissionRecord
from app.schemas import (
    AuditLogRead,
    BusinessMetricCreate,
    BusinessMetricRead,
    EmissionFactorRead,
    EmissionRecordCreate,
    EmissionRecordRead,
    OverrideCreate,
)
from app.seed import seed_database
from app.services.ai_insights import generate_insights
from app.services.analytics import (
    anomaly_payload,
    hotspot_payload,
    intensity_payload,
    monthly_trend_payload,
    net_zero_payload,
    yoy_payload,
)
from app.services.calculation import calculate_kgco2e, get_valid_factor


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(
    title=settings.app_name,
    description="GHG emissions reporting platform with versioned factors and analytics APIs.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"] if part != "body"),
            "message": error["msg"].removeprefix("Value error, "),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=400,
        content={"detail": "Request validation failed", "errors": errors},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/", include_in_schema=False)
def api_home() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.post("/admin/seed")
def seed(db: Session = Depends(get_db)) -> dict:
    return seed_database(db)


@app.get("/metadata/factors", response_model=list[EmissionFactorRead])
def list_factors(
    scope: str | None = None,
    active_on: date | None = None,
    db: Session = Depends(get_db),
) -> list[EmissionFactor]:
    stmt = select(EmissionFactor).order_by(
        EmissionFactor.scope,
        EmissionFactor.source_name,
        EmissionFactor.valid_from.desc(),
    )
    if scope:
        stmt = stmt.where(EmissionFactor.scope == scope)
    if active_on:
        stmt = stmt.where(
            EmissionFactor.valid_from <= active_on,
            (
                EmissionFactor.valid_to.is_(None)
                | (EmissionFactor.valid_to >= active_on)
            ),
        )
    return list(db.scalars(stmt).all())


def _create_record(
    db: Session, scope: str, payload: EmissionRecordCreate
) -> EmissionRecord:
    factor = get_valid_factor(
        db,
        scope=scope,
        source_name=payload.source_name,
        unit=payload.unit,
        activity_date=payload.activity_date,
    )
    emissions = calculate_kgco2e(payload.quantity, factor)
    record = EmissionRecord(
        scope=scope,
        activity_date=payload.activity_date,
        source_name=payload.source_name,
        activity_category=payload.activity_category,
        quantity=payload.quantity,
        unit=payload.unit,
        factor_id=factor.id,
        calculated_emissions_kgco2e=emissions,
        final_emissions_kgco2e=emissions,
        location=payload.location,
        notes=payload.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.post(
    "/emission-records/scope-1", response_model=EmissionRecordRead, status_code=201
)
def create_scope_1_record(
    payload: EmissionRecordCreate, db: Session = Depends(get_db)
) -> EmissionRecord:
    return _create_record(db, "Scope 1", payload)


@app.post(
    "/emission-records/scope-2", response_model=EmissionRecordRead, status_code=201
)
def create_scope_2_record(
    payload: EmissionRecordCreate, db: Session = Depends(get_db)
) -> EmissionRecord:
    return _create_record(db, "Scope 2", payload)


@app.post(
    "/emission-records/scope-3", response_model=EmissionRecordRead, status_code=201
)
def create_scope_3_record(
    payload: EmissionRecordCreate, db: Session = Depends(get_db)
) -> EmissionRecord:
    return _create_record(db, "Scope 3", payload)


@app.get("/emission-records", response_model=list[EmissionRecordRead])
def list_records(
    limit: int = Query(default=100, le=500),
    scope: str | None = None,
    db: Session = Depends(get_db),
) -> list[EmissionRecord]:
    stmt = (
        select(EmissionRecord)
        .order_by(EmissionRecord.activity_date.desc(), EmissionRecord.id.desc())
        .limit(limit)
    )
    if scope:
        stmt = stmt.where(EmissionRecord.scope == scope)
    return list(db.scalars(stmt).all())


@app.patch("/emission-records/{record_id}/override", response_model=EmissionRecordRead)
def override_record(
    record_id: int, payload: OverrideCreate, db: Session = Depends(get_db)
) -> EmissionRecord:
    record = db.get(EmissionRecord, record_id)
    if not record:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Emission record not found")
    old_value = record.final_emissions_kgco2e
    record.final_emissions_kgco2e = payload.new_emissions_kgco2e
    record.is_overridden = True
    db.add(
        AuditLog(
            record_id=record.id,
            old_value=old_value,
            new_value=payload.new_emissions_kgco2e,
            reason=payload.reason,
            changed_by=payload.changed_by,
        )
    )
    db.commit()
    db.refresh(record)
    return record


@app.get("/audit-logs", response_model=list[AuditLogRead])
def list_audit_logs(
    limit: int = Query(default=100, le=500), db: Session = Depends(get_db)
) -> list[AuditLog]:
    return list(
        db.scalars(
            select(AuditLog).order_by(AuditLog.changed_at.desc()).limit(limit)
        ).all()
    )


@app.post("/business-metrics", response_model=BusinessMetricRead, status_code=201)
def create_business_metric(
    payload: BusinessMetricCreate, db: Session = Depends(get_db)
) -> BusinessMetric:
    metric = BusinessMetric(**payload.model_dump())
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


@app.get("/business-metrics", response_model=list[BusinessMetricRead])
def list_business_metrics(
    metric_name: str | None = None, db: Session = Depends(get_db)
) -> list[BusinessMetric]:
    stmt = select(BusinessMetric).order_by(BusinessMetric.metric_date.desc())
    if metric_name:
        stmt = stmt.where(BusinessMetric.metric_name == metric_name)
    return list(db.scalars(stmt).all())


@app.get("/analytics/yoy")
def yoy(year: int = 2024, db: Session = Depends(get_db)) -> dict:
    return yoy_payload(db, year)


@app.get("/analytics/intensity")
def intensity(
    start_date: date = date(2024, 1, 1),
    end_date: date = date(2024, 12, 31),
    metric_name: str = "Tons of Steel Produced",
    db: Session = Depends(get_db),
) -> dict:
    return intensity_payload(db, start_date, end_date, metric_name)


@app.get("/analytics/hotspots")
def hotspots(
    start_date: date = date(2024, 1, 1),
    end_date: date = date(2024, 12, 31),
    limit: int = Query(default=10, ge=1, le=25),
    db: Session = Depends(get_db),
) -> list[dict]:
    return hotspot_payload(db, start_date, end_date, limit)


@app.get("/analytics/monthly-trend")
def monthly_trend(year: int = 2024, db: Session = Depends(get_db)) -> list[dict]:
    return monthly_trend_payload(db, year)


@app.get("/analytics/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    return {
        "yoy": yoy_payload(db, 2024),
        "intensity": intensity_payload(
            db, date(2024, 1, 1), date(2024, 12, 31), "Tons of Steel Produced"
        ),
        "hotspots": hotspot_payload(db, date(2024, 1, 1), date(2024, 12, 31), 5),
        "monthly_trend": monthly_trend_payload(db, 2024),
    }


@app.get("/analytics/anomalies")
def anomalies(
    year: int = 2024,
    threshold: float = Query(default=2.0, ge=1.0, le=5.0),
    db: Session = Depends(get_db),
) -> dict:
    return anomaly_payload(db, year, threshold)


@app.get("/analytics/net-zero")
def net_zero(
    current_year: int = 2024,
    baseline_year: int = 2023,
    target_year: int = 2030,
    target_reduction_pct: float = Query(default=50, gt=0, le=100),
    db: Session = Depends(get_db),
) -> dict:
    return net_zero_payload(
        db, current_year, baseline_year, target_year, target_reduction_pct
    )


@app.get("/analytics/ai-insights")
async def ai_insights(db: Session = Depends(get_db)) -> dict:
    analytics_data = {
        "yoy": yoy_payload(db, 2024),
        "intensity": intensity_payload(
            db,
            date(2024, 1, 1),
            date(2024, 12, 31),
            "Tons of Steel Produced",
        ),
        "hotspots": hotspot_payload(db, date(2024, 1, 1), date(2024, 12, 31), 5),
        "net_zero": net_zero_payload(db, 2024),
    }
    return await generate_insights(analytics_data)


@app.get("/metadata/scope-3-categories")
def scope_3_categories() -> dict:
    return {
        "status": "calculation-ready-when-factors-are-loaded",
        "categories": [
            "Purchased goods and services",
            "Capital goods",
            "Fuel- and energy-related activities",
            "Upstream transportation and distribution",
            "Waste generated in operations",
            "Business travel",
            "Employee commuting",
            "Upstream leased assets",
            "Downstream transportation and distribution",
            "Processing of sold products",
            "Use of sold products",
            "End-of-life treatment of sold products",
            "Downstream leased assets",
            "Franchises",
            "Investments",
        ],
    }


@app.get("/analytics/historical-accuracy-check")
def historical_accuracy_check(
    scope: str = "Scope 1",
    source_name: str = "Diesel",
    unit: str = "KL",
    quantity: float = 10,
    previous_date: date = date(2023, 6, 1),
    current_date: date = date(2024, 6, 1),
    db: Session = Depends(get_db),
) -> dict:
    previous_factor = get_valid_factor(
        db,
        scope=scope,
        source_name=source_name,
        unit=unit,
        activity_date=previous_date,
    )
    current_factor = get_valid_factor(
        db,
        scope=scope,
        source_name=source_name,
        unit=unit,
        activity_date=current_date,
    )
    return {
        "message": "The same activity uses the factor version valid on the activity date.",
        "input": {
            "scope": scope,
            "source_name": source_name,
            "unit": unit,
            "quantity": quantity,
        },
        "previous_period": {
            "activity_date": previous_date,
            "factor_id": previous_factor.id,
            "factor_version": previous_factor.version,
            "factor_kgco2e_per_unit": previous_factor.factor_kgco2e_per_unit,
            "calculated_kgco2e": calculate_kgco2e(quantity, previous_factor),
        },
        "current_period": {
            "activity_date": current_date,
            "factor_id": current_factor.id,
            "factor_version": current_factor.version,
            "factor_kgco2e_per_unit": current_factor.factor_kgco2e_per_unit,
            "calculated_kgco2e": calculate_kgco2e(quantity, current_factor),
        },
    }
