# CarbonSight GHG Platform

CarbonSight is a full-stack prototype for Scope 1 and Scope 2 greenhouse-gas reporting. It imports the supplied `GHG Sheet.xlsx`, stores versioned emission factors, calculates records with the factor valid on the activity date, exposes analytics APIs, and renders an ESG dashboard.

## Technology Stack

- Backend: FastAPI, SQLAlchemy, Python
- Database: PostgreSQL
- Frontend: React, TypeScript, Recharts
- Packaging: Docker Compose
- Seed data: `GHG Sheet.xlsx`

## Architecture

```mermaid
flowchart LR
  A["React ESG Dashboard"] --> B["FastAPI API Layer"]
  B --> C["Calculation Engine"]
  B --> D["Analytics Service"]
  C --> E["PostgreSQL"]
  D --> E
  F["GHG Sheet.xlsx Seeder"] --> E
```

## Data Model

The schema is built around master data and auditability:

- `emission_factors`: versioned factors with `valid_from`, `valid_to`, source, unit, and factor value in `kgCO2e/unit`.
- `emission_records`: recorded activity data linked to the exact factor version used during calculation.
- `audit_logs`: manual override trail with old value, new value, reason, user, and timestamp.
- `business_metrics`: denominator metrics over time, such as tons of steel produced.

This supports historical accuracy because the create-record API selects the emission factor whose validity window contains the activity date.

## Scoring Alignment

| Evaluation item | Implementation |
| --- | --- |
| Architecture and stack | Documented FastAPI + PostgreSQL + React architecture |
| Scalable schema | Versioned factors, emission records, business metrics, audit logs |
| YoY emissions API | `GET /analytics/yoy?year=2024` |
| Emission intensity API | `GET /analytics/intensity` |
| Hotspot API | `GET /analytics/hotspots` |
| Historical accuracy | Calculation engine chooses factors by activity date |
| Scope 1 and 2 record APIs | `POST /emission-records/scope-1`, `POST /emission-records/scope-2` |
| Manual overrides | Dashboard override form, `PATCH /emission-records/{id}/override`, and `GET /audit-logs` |
| Frontend forms | Emission record form and business metric form |
| Required charts | Stacked YoY bar, hotspot donut, intensity KPI, monthly trend line |

## Run with Docker

```bash
docker compose up --build
```

Open:

- Frontend: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

The backend automatically creates tables and seeds PostgreSQL from `GHG Sheet.xlsx` on startup. The seed includes 2024 records imported from the workbook plus generated 2023 comparison records that use expired factor versions.

## Key API Examples

Create a Scope 1 record:

```bash
curl -X POST http://localhost:8000/emission-records/scope-1 \
  -H "Content-Type: application/json" \
  -d '{
    "activity_date": "2024-07-15",
    "source_name": "Diesel",
    "activity_category": "Stationary Combustion",
    "quantity": 100,
    "unit": "KL",
    "location": "Central Steel Plant"
  }'
```

Override a calculated value:

```bash
curl -X PATCH http://localhost:8000/emission-records/1/override \
  -H "Content-Type: application/json" \
  -d '{
    "new_emissions_kgco2e": 250000,
    "reason": "Corrected meter reading after invoice reconciliation",
    "changed_by": "admin@demo.com"
  }'
```

Analytics:

```bash
curl "http://localhost:8000/analytics/yoy?year=2024"
curl "http://localhost:8000/analytics/intensity?start_date=2024-01-01&end_date=2024-12-31&metric_name=Tons%20of%20Steel%20Produced"
curl "http://localhost:8000/analytics/hotspots?start_date=2024-01-01&end_date=2024-12-31"
curl "http://localhost:8000/analytics/monthly-trend?year=2024"
curl "http://localhost:8000/analytics/historical-accuracy-check?source_name=Diesel&unit=KL"
```

The historical accuracy check returns two calculations for the same activity quantity: one using the expired 2023 factor and one using the active 2024 factor. This directly demonstrates that records are calculated with the factor valid on the activity date, not simply the latest factor.

## Local Backend Development

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/ghg_platform"
uvicorn app.main:app --reload
```

Run tests:

```bash
cd backend
pytest
```

## Local Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## Notes for Evaluators

- Emissions are stored in `kgCO2e` for consistency and displayed as `tCO2e` on the dashboard where readability matters.
- Scope 3 data exists in the workbook, but the prototype intentionally focuses on Scope 1 and Scope 2 because the assignment prioritizes those scopes.
- Manual overrides do not destroy calculated values; they preserve the original calculation and add an audit record.
