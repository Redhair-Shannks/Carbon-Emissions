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
  U["Evaluator / ESG Analyst"] --> F["React + TypeScript Dashboard"]
  F -->|"HTTP / JSON"| A["FastAPI API"]
  A --> C["Historical Calculation Engine"]
  A --> R["Analytics and Reporting Engine"]
  A --> O["Override and Audit Service"]
  C --> S["SQLAlchemy ORM"]
  R --> S
  O --> S
  S --> P[("PostgreSQL")]
  W["GHG Sheet.xlsx"] --> I["Idempotent Seeder"]
  I --> P
  D["Docker Compose"] -.-> F
  D -.-> A
  D -.-> P
```

All application services run through Docker Compose. PostgreSQL stores
`EmissionFactors`, `EmissionRecords`, `BusinessMetrics`, and `AuditLogs`.

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

## Quick Start (3 Commands)

### Prerequisites

- Docker Desktop installed and running
- Git

### Run the Project

```bash
git clone https://github.com/Redhair-Shannks/Carbon-Emissions.git
cd Carbon-Emissions
docker compose up --build
```

### Access

| Service | URL |
| --- | --- |
| Frontend dashboard | <http://localhost:5173> |
| Backend API | <http://localhost:8000> |
| Swagger documentation | <http://localhost:8000/docs> |
| Health check | <http://localhost:8000/health> |
| Historical accuracy proof | <http://localhost:8000/analytics/historical-accuracy-check> |

The backend automatically creates tables and seeds PostgreSQL from `GHG Sheet.xlsx` on startup. The seed includes 2024 records imported from the workbook plus generated 2023 comparison records that use expired factor versions.

## Product Screenshots

### ESG Analytics Dashboard

![CarbonSight analytics dashboard](docs/screenshots/dashboard.png)

### Year-over-Year Scope Comparison

![Year-over-year Scope 1 and Scope 2 chart](docs/screenshots/yoy-chart.png)

### Interactive API Documentation

![FastAPI Swagger documentation](docs/screenshots/swagger-docs.png)

## Historical Accuracy Engine (Key Feature)

A 2023 Diesel activity always uses the emission factor valid in 2023, even
when a newer factor exists. Factor selection occurs at write time and the
chosen `factor_id` is permanently linked to the emission record.

Verify the behavior directly:

```text
GET /analytics/historical-accuracy-check?source_name=Diesel&unit=KL
```

The response shows the same quantity calculated once with the
`2023-expired` factor and once with the `2024-active` factor. This is direct,
machine-verifiable evidence that the platform does not recalculate history
using the latest factor.

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
pytest -q
```

The suite covers:

- Year-over-year Scope 1 and Scope 2 totals
- Ranked emission hotspots and contribution percentages
- Emission-intensity calculations
- Historical factor selection by activity date
- Scope 2 record creation and factor linkage
- Manual overrides and immutable audit entries
- Missing-factor, future-date, and non-positive quantity errors

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
- API request validation returns structured client errors instead of unhandled server exceptions.

## Optional Public Deployment

The repository includes `render.yaml`, which prepares a Render Blueprint with
a managed PostgreSQL database, FastAPI Docker service, React static site, and
backend health check. To publish it, connect this repository in Render and
create a new Blueprint. Review the generated service URLs and update
`CORS_ORIGINS` or `VITE_API_BASE_URL` if Render assigns different names.
