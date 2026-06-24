from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, EmissionFactor, EmissionRecord


def test_api_root_redirects_to_docs(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_ai_insights_returns_three_fallback_insights_without_api_key(
    client: TestClient,
) -> None:
    response = client.get("/analytics/ai-insights")

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_by"] == "deterministic-analytics"
    assert len(payload["insights"]) == 3


def test_scope_3_categories_expose_ghg_protocol_skeleton(client: TestClient) -> None:
    response = client.get("/metadata/scope-3-categories")

    assert response.status_code == 200
    assert len(response.json()["categories"]) == 15


def add_scope_2_factor(db: Session) -> EmissionFactor:
    factor = EmissionFactor(
        scope="Scope 2",
        source_name="Grid Electricity",
        activity_category="Purchased Electricity",
        unit="kWh",
        factor_kgco2e_per_unit=0.82,
        factor_unit="kgCO2e/kWh",
        source="Test grid authority",
        version="2024-active",
        valid_from=date(2024, 1, 1),
        valid_to=None,
    )
    db.add(factor)
    db.commit()
    db.refresh(factor)
    return factor


def test_scope2_record_creation(client: TestClient, db: Session) -> None:
    factor = add_scope_2_factor(db)

    response = client.post(
        "/emission-records/scope-2",
        json={
            "activity_date": "2024-06-15",
            "source_name": "Grid Electricity",
            "activity_category": "Purchased Electricity",
            "quantity": 1000,
            "unit": "kWh",
            "location": "Main Plant",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["scope"] == "Scope 2"
    assert payload["factor_id"] == factor.id
    assert payload["calculated_emissions_kgco2e"] == 820
    assert payload["final_emissions_kgco2e"] == 820


def test_override_creates_audit_entry(client: TestClient, db: Session) -> None:
    add_scope_2_factor(db)
    created = client.post(
        "/emission-records/scope-2",
        json={
            "activity_date": "2024-06-15",
            "source_name": "Grid Electricity",
            "activity_category": "Purchased Electricity",
            "quantity": 1000,
            "unit": "kWh",
        },
    ).json()

    response = client.patch(
        f"/emission-records/{created['id']}/override",
        json={
            "new_emissions_kgco2e": 790,
            "reason": "Invoice reconciliation correction",
            "changed_by": "reviewer@example.com",
        },
    )

    assert response.status_code == 200
    assert response.json()["is_overridden"] is True
    assert response.json()["final_emissions_kgco2e"] == 790

    record = db.get(EmissionRecord, created["id"])
    audit = db.scalar(select(AuditLog).where(AuditLog.record_id == created["id"]))
    assert record is not None
    assert record.calculated_emissions_kgco2e == 820
    assert audit is not None
    assert audit.old_value == 820
    assert audit.new_value == 790
    assert audit.reason == "Invoice reconciliation correction"
    assert audit.changed_by == "reviewer@example.com"


def test_missing_factor_returns_clean_404(client: TestClient) -> None:
    response = client.post(
        "/emission-records/scope-1",
        json={
            "activity_date": "2024-06-15",
            "source_name": "Unknown Fuel",
            "activity_category": "Stationary Combustion",
            "quantity": 100,
            "unit": "litres",
        },
    )

    assert response.status_code == 404
    assert "No emission factor is valid" in response.json()["detail"]


def test_future_activity_date_returns_clean_400(client: TestClient) -> None:
    response = client.post(
        "/emission-records/scope-1",
        json={
            "activity_date": str(date.today() + timedelta(days=1)),
            "source_name": "Diesel",
            "activity_category": "Stationary Combustion",
            "quantity": 100,
            "unit": "KL",
        },
    )

    assert response.status_code == 400
    assert response.json()["errors"] == [
        {"field": "activity_date", "message": "Activity date cannot be in the future"}
    ]


def test_non_positive_quantity_returns_clean_400(client: TestClient) -> None:
    response = client.post(
        "/emission-records/scope-1",
        json={
            "activity_date": "2024-06-15",
            "source_name": "Diesel",
            "activity_category": "Stationary Combustion",
            "quantity": 0,
            "unit": "KL",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Request validation failed"
    assert response.json()["errors"][0]["field"] == "quantity"
