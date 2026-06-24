from datetime import date
from math import sqrt

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.models import BusinessMetric, EmissionRecord


def totals_by_scope_for_year(db: Session, year: int) -> dict[str, float]:
    stmt = (
        select(
            EmissionRecord.scope,
            func.coalesce(func.sum(EmissionRecord.final_emissions_kgco2e), 0),
        )
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


def intensity_payload(
    db: Session, start_date: date, end_date: date, metric_name: str
) -> dict:
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


def hotspot_payload(
    db: Session, start_date: date, end_date: date, limit: int = 10
) -> list[dict]:
    total_emissions = float(
        db.scalar(
            select(
                func.coalesce(func.sum(EmissionRecord.final_emissions_kgco2e), 0)
            ).where(
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
            func.coalesce(func.sum(EmissionRecord.final_emissions_kgco2e), 0).label(
                "emissions"
            ),
        )
        .where(
            EmissionRecord.activity_date >= start_date,
            EmissionRecord.activity_date <= end_date,
        )
        .group_by(EmissionRecord.source_name, EmissionRecord.scope)
        .order_by(func.sum(EmissionRecord.final_emissions_kgco2e).desc())
        .limit(limit)
    )
    return [
        {
            "source_name": source,
            "scope": scope,
            "emissions_kgco2e": float(emissions or 0),
            "share_pct": (
                (float(emissions or 0) / total_emissions * 100)
                if total_emissions
                else 0
            ),
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
        month: {
            "month": f"{year}-{month:02d}",
            "scope_1_kgco2e": 0.0,
            "scope_2_kgco2e": 0.0,
            "total_kgco2e": 0.0,
        }
        for month in range(1, 13)
    }
    for month_raw, scope, total in rows:
        month = int(month_raw)
        key = f"{scope.lower().replace(' ', '_')}_kgco2e"
        if key in months[month]:
            months[month][key] = float(total or 0)
        months[month]["total_kgco2e"] += float(total or 0)
    return list(months.values())


def anomaly_payload(db: Session, year: int, threshold: float = 2.0) -> dict:
    records = list(
        db.scalars(
            select(EmissionRecord)
            .where(extract("year", EmissionRecord.activity_date) == year)
            .order_by(EmissionRecord.activity_date, EmissionRecord.id)
        ).all()
    )
    grouped: dict[tuple[str, str], list[EmissionRecord]] = {}
    for record in records:
        grouped.setdefault((record.scope, record.source_name), []).append(record)

    anomalies = []
    for group_records in grouped.values():
        if len(group_records) < 4:
            continue
        values = [float(record.final_emissions_kgco2e) for record in group_records]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        std_dev = sqrt(variance)
        if std_dev == 0:
            continue

        for record in group_records:
            z_score = (float(record.final_emissions_kgco2e) - mean) / std_dev
            if abs(z_score) > threshold:
                anomalies.append(
                    {
                        "record_id": record.id,
                        "activity_date": record.activity_date,
                        "source_name": record.source_name,
                        "scope": record.scope,
                        "emissions_kgco2e": float(record.final_emissions_kgco2e),
                        "z_score": round(z_score, 2),
                        "severity": "high" if abs(z_score) > 3 else "medium",
                    }
                )

    anomalies.sort(key=lambda item: abs(item["z_score"]), reverse=True)
    return {
        "year": year,
        "method": "Within-source population z-score",
        "threshold": threshold,
        "minimum_group_size": 4,
        "anomalies": anomalies,
        "total_flagged": len(anomalies),
    }


def net_zero_payload(
    db: Session,
    current_year: int,
    baseline_year: int = 2023,
    target_year: int = 2030,
    target_reduction_pct: float = 50,
) -> dict:
    baseline = totals_by_scope_for_year(db, baseline_year)["total_kgco2e"]
    current = totals_by_scope_for_year(db, current_year)["total_kgco2e"]
    target = baseline * (1 - target_reduction_pct / 100)
    achieved_reduction = baseline - current
    required_reduction = baseline - target
    progress_pct = (
        (achieved_reduction / required_reduction * 100) if required_reduction > 0 else 0
    )
    progress_pct = max(0.0, min(100.0, progress_pct))
    gap = max(0.0, current - target)

    return {
        "baseline_year": baseline_year,
        "current_year": current_year,
        "target_year": target_year,
        "target_reduction_pct": target_reduction_pct,
        "baseline_emissions_kgco2e": baseline,
        "current_emissions_kgco2e": current,
        "target_emissions_kgco2e": target,
        "gap_to_target_kgco2e": gap,
        "progress_pct": progress_pct,
        "status": "on-track" if current <= target else "action-required",
    }
