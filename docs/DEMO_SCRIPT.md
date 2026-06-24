# CarbonSight Four-Minute Walkthrough

## 0:00 - 0:30: Architecture and startup

- Show the repository README and architecture diagram.
- Run `docker compose up --build`.
- Confirm the three healthy services with `docker compose ps`.

## 0:30 - 1:30: Analytics dashboard

- Open `http://localhost:5173`.
- Point out the Scope 1 and 2 KPI, intensity metric, YoY stacked chart, hotspot
  donut, and monthly trend.
- Highlight AI Narrative Insights, anomaly badges, and the 2030 target tracker.

## 1:30 - 2:20: Historical accuracy

- Open `http://localhost:8000/analytics/historical-accuracy-check`.
- Compare `2023-expired` with `2024-active`.
- Explain that every record permanently stores the selected factor ID.

## 2:20 - 3:10: Record creation and auditability

- Create one Scope 1 record from the dashboard.
- Show the inline success message and refreshed analytics.
- Apply a manual override and show the new audit-trail entry.

## 3:10 - 4:00: Engineering quality

- Open Swagger at `http://localhost:8000/docs`.
- Show anomaly, net-zero, AI insight, and Scope 3 metadata endpoints.
- Finish on the GitHub Actions badge and the passing test suite.
