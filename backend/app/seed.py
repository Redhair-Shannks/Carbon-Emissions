from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BusinessMetric, EmissionFactor, EmissionRecord


QUARTER_MONTHS = {
    "Q1": [1, 2, 3],
    "Q2": [4, 5, 6],
    "Q3": [7, 8, 9],
    "Q4": [10, 11, 12],
}


def _date_for_quarter(quarter: str, year: int, index: int) -> date:
    months = QUARTER_MONTHS.get(str(quarter).strip(), [1])
    return date(year, months[index % len(months)], min(28, 5 + (index % 20)))


def _add_factor_versions(
    db: Session,
    *,
    scope: str,
    source_name: str,
    activity_category: str,
    unit: str,
    factor_tco2e_per_unit: float,
    source: str,
) -> None:
    if db.scalar(
        select(EmissionFactor.id).where(
            EmissionFactor.scope == scope,
            EmissionFactor.source_name == source_name,
            EmissionFactor.unit == unit,
        )
    ):
        return
    base_kg = float(factor_tco2e_per_unit) * 1000
    db.add_all(
        [
            EmissionFactor(
                scope=scope,
                source_name=source_name,
                activity_category=activity_category,
                unit=unit,
                factor_kgco2e_per_unit=round(base_kg * 0.94, 6),
                factor_unit=f"kgCO2e/{unit}",
                source=f"{source} - historical version",
                version="2023-expired",
                valid_from=date(2023, 1, 1),
                valid_to=date(2023, 12, 31),
            ),
            EmissionFactor(
                scope=scope,
                source_name=source_name,
                activity_category=activity_category,
                unit=unit,
                factor_kgco2e_per_unit=round(base_kg, 6),
                factor_unit=f"kgCO2e/{unit}",
                source=source,
                version="2024-active",
                valid_from=date(2024, 1, 1),
                valid_to=date(2024, 12, 31),
            ),
            EmissionFactor(
                scope=scope,
                source_name=source_name,
                activity_category=activity_category,
                unit=unit,
                factor_kgco2e_per_unit=round(base_kg * 1.03, 6),
                factor_unit=f"kgCO2e/{unit}",
                source=f"{source} - updated version",
                version="2025-current",
                valid_from=date(2025, 1, 1),
                valid_to=None,
            ),
        ]
    )


def _factor_for(
    db: Session, scope: str, source_name: str, unit: str, activity_date: date
) -> EmissionFactor:
    return db.scalars(
        select(EmissionFactor)
        .where(
            EmissionFactor.scope == scope,
            EmissionFactor.source_name == source_name,
            EmissionFactor.unit == unit,
            EmissionFactor.valid_from <= activity_date,
            (
                EmissionFactor.valid_to.is_(None)
                | (EmissionFactor.valid_to >= activity_date)
            ),
        )
        .order_by(EmissionFactor.valid_from.desc())
    ).first()


def _add_record(
    db: Session,
    *,
    scope: str,
    activity_date: date,
    source_name: str,
    activity_category: str,
    quantity: float,
    unit: str,
    location: str | None,
    notes: str | None = None,
) -> None:
    factor = _factor_for(db, scope, source_name, unit, activity_date)
    if not factor:
        return
    emissions = round(float(quantity) * factor.factor_kgco2e_per_unit, 6)
    db.add(
        EmissionRecord(
            scope=scope,
            activity_date=activity_date,
            source_name=source_name,
            activity_category=activity_category,
            quantity=float(quantity),
            unit=unit,
            factor_id=factor.id,
            calculated_emissions_kgco2e=emissions,
            final_emissions_kgco2e=emissions,
            location=location,
            notes=notes,
        )
    )


def seed_database(db: Session) -> dict[str, int | str]:
    if db.scalar(select(EmissionRecord.id).limit(1)):
        return {
            "status": "skipped",
            "reason": "database already contains emission records",
        }

    workbook_path = Path(settings.seed_workbook_path)
    if not workbook_path.is_absolute():
        candidates = [
            Path.cwd() / workbook_path,
            Path(__file__).resolve().parents[2] / workbook_path,
            Path(__file__).resolve().parents[1] / workbook_path,
        ]
        workbook_path = next(
            (candidate.resolve() for candidate in candidates if candidate.exists()),
            candidates[0].resolve(),
        )
    if not workbook_path.exists():
        return {"status": "missing_workbook", "path": str(workbook_path)}

    scope1 = pd.read_excel(workbook_path, sheet_name="Scope 1")
    scope2 = pd.read_excel(workbook_path, sheet_name="Scope 2")

    for _, row in scope1.dropna(
        subset=["Material", "Emission Factor", "Q1 Quantity"]
    ).iterrows():
        _add_factor_versions(
            db,
            scope="Scope 1",
            source_name=str(row["Material"]),
            activity_category=str(row["Section"]),
            unit=str(row["Unit of Material"]),
            factor_tco2e_per_unit=float(row["Emission Factor"]),
            source=str(row["Data Source for Emission Factor"]),
        )

    for _, row in scope2.dropna(
        subset=["Supplier/Source", "Emission Factor (tCO₂/unit)", "Energy Consumed"]
    ).iterrows():
        _add_factor_versions(
            db,
            scope="Scope 2",
            source_name=str(row["Supplier/Source"]),
            activity_category=str(row["Energy Type"]),
            unit=str(row["Unit"]),
            factor_tco2e_per_unit=float(row["Emission Factor (tCO₂/unit)"]),
            source=str(row["Grid Emission Factor Source"]),
        )

    db.flush()

    for index, row in scope1.dropna(subset=["Material", "Q1 Quantity"]).iterrows():
        activity_date = _date_for_quarter(str(row["Year/Timeline"]), 2024, int(index))
        _add_record(
            db,
            scope="Scope 1",
            activity_date=activity_date,
            source_name=str(row["Material"]),
            activity_category=str(row["Section"]),
            quantity=float(row["Q1 Quantity"]),
            unit=str(row["Unit of Material"]),
            location=str(row["Location (Plant)"]),
            notes="Imported from Scope 1 workbook sheet",
        )
        previous_year_date = date(2023, activity_date.month, activity_date.day)
        _add_record(
            db,
            scope="Scope 1",
            activity_date=previous_year_date,
            source_name=str(row["Material"]),
            activity_category=str(row["Section"]),
            quantity=float(row["Q1 Quantity"]) * 0.92,
            unit=str(row["Unit of Material"]),
            location=str(row["Location (Plant)"]),
            notes="Generated prior-year comparison record using expired factor version",
        )

    for index, row in scope2.dropna(
        subset=["Supplier/Source", "Energy Consumed"]
    ).iterrows():
        activity_date = _date_for_quarter(str(row["Quarter"]), 2024, int(index))
        _add_record(
            db,
            scope="Scope 2",
            activity_date=activity_date,
            source_name=str(row["Supplier/Source"]),
            activity_category=str(row["Energy Type"]),
            quantity=float(row["Energy Consumed"]),
            unit=str(row["Unit"]),
            location=str(row["Location (Plant)"]),
            notes="Imported from Scope 2 workbook sheet",
        )
        previous_year_date = date(2023, activity_date.month, activity_date.day)
        _add_record(
            db,
            scope="Scope 2",
            activity_date=previous_year_date,
            source_name=str(row["Supplier/Source"]),
            activity_category=str(row["Energy Type"]),
            quantity=float(row["Energy Consumed"]) * 0.9,
            unit=str(row["Unit"]),
            location=str(row["Location (Plant)"]),
            notes="Generated prior-year comparison record using expired factor version",
        )

    for year, monthly_base in [(2023, 38000), (2024, 43000)]:
        for month in range(1, 13):
            db.add(
                BusinessMetric(
                    metric_date=date(year, month, 28),
                    metric_name="Tons of Steel Produced",
                    value=monthly_base + (month * 850),
                    unit="tonnes",
                )
            )
            db.add(
                BusinessMetric(
                    metric_date=date(year, month, 28),
                    metric_name="Employees",
                    value=1280 + (month % 4) * 12,
                    unit="employees",
                )
            )

    db.commit()
    return {"status": "seeded", "scope1_rows": len(scope1), "scope2_rows": len(scope2)}
