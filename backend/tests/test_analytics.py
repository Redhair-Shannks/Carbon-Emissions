from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models import BusinessMetric, EmissionFactor, EmissionRecord
from app.services.analytics import (
    anomaly_payload,
    hotspot_payload,
    intensity_payload,
    net_zero_payload,
    yoy_payload,
)


def add_factor(
    db: Session,
    *,
    scope: str,
    source_name: str,
    factor: float,
    valid_from: date,
    valid_to: date | None = None,
) -> EmissionFactor:
    row = EmissionFactor(
        scope=scope,
        source_name=source_name,
        activity_category="Test category",
        unit="unit",
        factor_kgco2e_per_unit=factor,
        factor_unit="kgCO2e/unit",
        source="Test source",
        version=str(valid_from.year),
        valid_from=valid_from,
        valid_to=valid_to,
    )
    db.add(row)
    db.flush()
    return row


def add_record(
    db: Session,
    *,
    factor: EmissionFactor,
    activity_date: date,
    emissions: float,
) -> None:
    db.add(
        EmissionRecord(
            scope=factor.scope,
            activity_date=activity_date,
            source_name=factor.source_name,
            activity_category=factor.activity_category,
            quantity=1,
            unit=factor.unit,
            factor_id=factor.id,
            calculated_emissions_kgco2e=emissions,
            final_emissions_kgco2e=emissions,
        )
    )


def seed_analytics_data(db: Session) -> None:
    diesel_2023 = add_factor(
        db,
        scope="Scope 1",
        source_name="Diesel",
        factor=100,
        valid_from=date(2023, 1, 1),
        valid_to=date(2023, 12, 31),
    )
    grid_2023 = add_factor(
        db,
        scope="Scope 2",
        source_name="Grid Electricity",
        factor=100,
        valid_from=date(2023, 1, 1),
        valid_to=date(2023, 12, 31),
    )
    diesel_2024 = add_factor(
        db,
        scope="Scope 1",
        source_name="Diesel",
        factor=100,
        valid_from=date(2024, 1, 1),
    )
    gas_2024 = add_factor(
        db,
        scope="Scope 1",
        source_name="Natural Gas",
        factor=100,
        valid_from=date(2024, 1, 1),
    )
    grid_2024 = add_factor(
        db,
        scope="Scope 2",
        source_name="Grid Electricity",
        factor=100,
        valid_from=date(2024, 1, 1),
    )

    add_record(db, factor=diesel_2023, activity_date=date(2023, 6, 1), emissions=100)
    add_record(db, factor=grid_2023, activity_date=date(2023, 6, 1), emissions=200)
    add_record(db, factor=diesel_2024, activity_date=date(2024, 3, 1), emissions=300)
    add_record(db, factor=gas_2024, activity_date=date(2024, 4, 1), emissions=100)
    add_record(db, factor=grid_2024, activity_date=date(2024, 5, 1), emissions=400)
    db.add(
        BusinessMetric(
            metric_date=date(2024, 12, 31),
            metric_name="Tons of Steel Produced",
            value=100,
            unit="tonnes",
        )
    )
    db.commit()


def test_yoy_returns_scope1_and_scope2(db: Session) -> None:
    seed_analytics_data(db)

    result = yoy_payload(db, 2024)

    assert result["selected_year"]["scope_1_kgco2e"] == 400
    assert result["selected_year"]["scope_2_kgco2e"] == 400
    assert result["selected_year"]["total_kgco2e"] == 800
    assert result["previous_year"]["scope_1_kgco2e"] == 100
    assert result["previous_year"]["scope_2_kgco2e"] == 200


def test_hotspot_returns_ranked_sources(db: Session) -> None:
    seed_analytics_data(db)

    result = hotspot_payload(db, date(2024, 1, 1), date(2024, 12, 31))

    assert [row["source_name"] for row in result] == [
        "Grid Electricity",
        "Diesel",
        "Natural Gas",
    ]
    assert result[0]["share_pct"] == pytest.approx(50)
    assert result[1]["share_pct"] == pytest.approx(37.5)


def test_intensity_calculation_is_correct(db: Session) -> None:
    seed_analytics_data(db)

    result = intensity_payload(
        db,
        date(2024, 1, 1),
        date(2024, 12, 31),
        "Tons of Steel Produced",
    )

    assert result["total_emissions_kgco2e"] == 800
    assert result["business_metric_value"] == 100
    assert result["intensity_kgco2e_per_unit"] == 8


def test_anomaly_detection_flags_source_outlier(db: Session) -> None:
    factor = add_factor(
        db,
        scope="Scope 1",
        source_name="Diesel",
        factor=1,
        valid_from=date(2024, 1, 1),
    )
    for month, emissions in enumerate([100, 100, 100, 100, 100, 1000], start=1):
        add_record(
            db,
            factor=factor,
            activity_date=date(2024, month, 1),
            emissions=emissions,
        )
    db.commit()

    result = anomaly_payload(db, 2024)

    assert result["total_flagged"] == 1
    assert result["anomalies"][0]["source_name"] == "Diesel"
    assert result["anomalies"][0]["emissions_kgco2e"] == 1000
    assert result["anomalies"][0]["z_score"] > 2


def test_net_zero_tracker_calculates_target_and_progress(db: Session) -> None:
    seed_analytics_data(db)

    result = net_zero_payload(
        db,
        current_year=2024,
        baseline_year=2023,
        target_year=2030,
        target_reduction_pct=50,
    )

    assert result["baseline_emissions_kgco2e"] == 300
    assert result["current_emissions_kgco2e"] == 800
    assert result["target_emissions_kgco2e"] == 150
    assert result["progress_pct"] == 0
    assert result["status"] == "action-required"
