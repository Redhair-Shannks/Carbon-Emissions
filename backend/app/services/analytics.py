from datetime import date

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.models import BusinessMetric, EmissionRecord


def totals_by_scope_for_year(db: Session, year: int) -> dict[str, float]:
    stmt = (
        select(EmissionRecord.scope, func.coalesce(func.sum(EmissionRecord.final_emissions_kgco2e), 0))
        .where(extract("year", EmissionRecord.activity_date) == year)
        .group_by(EmissionRecord.scope)
    )
    rows = db.execute(stmt).all()
    result = {"scope_1_kgco2e": 0.0, "scope_2_kgco2e": 0.0, "scope_3_kgco2e": 0.0}
    for scope, total in rows:
        key = f"{scope.lower().replace(' ', '_')}_kgco2e"
        result[key] = float(total or 0)
    result["total_kgco2e"] = sum(result.values())
    return result


def yoy_payload(db: Session, year: int) -> dict:
    return {
        "selected_year": {"year": year, **totals_by_scope_for_year(db, year)},
        "previous_year": {"year": year - 1, **totals_by_scope_for_year(db, year - 1)},
    }


def intensity_payload(db: Session, start_date: date, end_date: date, metric_name: str) -> dict:
    emissions = db.scalar(
        select(func.coalesce(func.sum(EmissionRecord.final_emissions_kgco2e), 0)).where(
            EmissionRecord.activity_date >= start_date,
            EmissionRecord.activity_date <= end_date,
            EmissionRecord.scope.in_(["Scope 1", "Scope 2"]),
        )
    )
    metric = db.scalar(
        select(func.coalesce(func.sum(BusinessMetric.value), 0)).where(
            BusinessMetric.metric_date >= start_date,
            BusinessMetric.metric_date <= end_date,
            BusinessMetric.metric_name == metric_name,
        )
    )
    emissions = float(emissions or 0)
    metric = float(metric or 0)
    intensity = emissions / metric if metric else None
    return {
        "start_date": start_date,
        "end_date": end_date,
        "metric_name": metric_name,
        "total_emissions_kgco2e": emissions,
        "business_metric_value": metric,
        "intensity_kgco2e_per_unit": intensity,
    }


def hotspot_payload(db: Session, start_date: date, end_date: date, limit: int = 10) -> list[dict]:
    total_emissions = float(
        db.scalar(
            select(func.coalesce(func.sum(EmissionRecord.final_emissions_kgco2e), 0)).where(
                EmissionRecord.activity_date >= start_date,
                EmissionRecord.activity_date <= end_date,
            )
        )
        or 0
    )
    stmt = (
        select(
            EmissionRecord.source_name,
            EmissionRecord.scope,
            func.coalesce(func.sum(EmissionRecord.final_emissions_kgco2e), 0).label("emissions"),
        )
        .where(EmissionRecord.activity_date >= start_date, EmissionRecord.activity_date <= end_date)
        .group_by(EmissionRecord.source_name, EmissionRecord.scope)
        .order_by(func.sum(EmissionRecord.final_emissions_kgco2e).desc())
        .limit(limit)
    )
    return [
        {
            "source_name": source,
            "scope": scope,
            "emissions_kgco2e": float(emissions or 0),
            "share_pct": (float(emissions or 0) / total_emissions * 100) if total_emissions else 0,
        }
        for source, scope, emissions in db.execute(stmt).all()
    ]


def monthly_trend_payload(db: Session, year: int) -> list[dict]:
    stmt = (
        select(
            extract("month", EmissionRecord.activity_date).label("month"),
            EmissionRecord.scope,
            func.coalesce(func.sum(EmissionRecord.final_emissions_kgco2e), 0),
        )
        .where(extract("year", EmissionRecord.activity_date) == year)
        .group_by("month", EmissionRecord.scope)
        .order_by("month")
    )
    rows = db.execute(stmt).all()
    months = {
        month: {"month": f"{year}-{month:02d}", "scope_1_kgco2e": 0.0, "scope_2_kgco2e": 0.0, "total_kgco2e": 0.0}
        for month in range(1, 13)
    }
    for month_raw, scope, total in rows:
        month = int(month_raw)
        key = f"{scope.lower().replace(' ', '_')}_kgco2e"
        if key in months[month]:
            months[month][key] = float(total or 0)
        months[month]["total_kgco2e"] += float(total or 0)
    return list(months.values())
