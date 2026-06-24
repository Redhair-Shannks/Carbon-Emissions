import React from "react";
import ReactDOM from "react-dom/client";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  Database,
  Factory,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type YoyPayload = {
  selected_year: YearTotals;
  previous_year: YearTotals;
};

type YearTotals = {
  year: number;
  scope_1_kgco2e: number;
  scope_2_kgco2e: number;
  total_kgco2e: number;
};

type IntensityPayload = {
  total_emissions_kgco2e: number;
  business_metric_value: number;
  intensity_kgco2e_per_unit: number | null;
  metric_name: string;
};

type Hotspot = {
  source_name: string;
  scope: string;
  emissions_kgco2e: number;
  share_pct: number;
};

type TrendRow = {
  month: string;
  scope_1_kgco2e: number;
  scope_2_kgco2e: number;
  total_kgco2e: number;
};

type Factor = {
  id: number;
  scope: string;
  source_name: string;
  activity_category: string;
  unit: string;
  factor_kgco2e_per_unit: number;
  version: string;
};

type EmissionRecord = {
  id: number;
  scope: string;
  activity_date: string;
  source_name: string;
  quantity: number;
  unit: string;
  calculated_emissions_kgco2e: number;
  final_emissions_kgco2e: number;
  is_overridden: boolean;
};

type AuditLog = {
  id: number;
  record_id: number;
  old_value: number;
  new_value: number;
  reason: string;
  changed_by: string;
  changed_at: string;
};

type Summary = {
  yoy: YoyPayload;
  intensity: IntensityPayload;
  hotspots: Hotspot[];
  monthly_trend: TrendRow[];
};

type InsightPayload = {
  insights: string[];
  generated_by: "anthropic" | "deterministic-analytics";
  model: string | null;
  notice: string | null;
};

type Anomaly = {
  record_id: number;
  activity_date: string;
  source_name: string;
  scope: string;
  emissions_kgco2e: number;
  z_score: number;
  severity: "medium" | "high";
};

type AnomalyPayload = {
  anomalies: Anomaly[];
  total_flagged: number;
  method: string;
};

type NetZeroPayload = {
  baseline_year: number;
  current_year: number;
  target_year: number;
  target_reduction_pct: number;
  target_emissions_kgco2e: number;
  gap_to_target_kgco2e: number;
  progress_pct: number;
  status: "on-track" | "action-required";
};

const COLORS = ["#167c80", "#8f5d13", "#345c96", "#6f7d1c", "#9d4b4b", "#5d5a92", "#c2762f", "#487a54"];

function tonnes(value: number) {
  return `${(value / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} tCO2e`;
}

function compactKg(value: number) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function App() {
  const initialLoadStarted = React.useRef(false);
  const [summary, setSummary] = React.useState<Summary | null>(null);
  const [factors, setFactors] = React.useState<Factor[]>([]);
  const [records, setRecords] = React.useState<EmissionRecord[]>([]);
  const [auditLogs, setAuditLogs] = React.useState<AuditLog[]>([]);
  const [insightPayload, setInsightPayload] = React.useState<InsightPayload | null>(null);
  const [anomalyPayload, setAnomalyPayload] = React.useState<AnomalyPayload | null>(null);
  const [netZeroPayload, setNetZeroPayload] = React.useState<NetZeroPayload | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [intelligenceLoading, setIntelligenceLoading] = React.useState(true);
  const [message, setMessage] = React.useState("");
  const [recordMessage, setRecordMessage] = React.useState("");
  const [metricMessage, setMetricMessage] = React.useState("");
  const [overrideMessage, setOverrideMessage] = React.useState("");
  const [savingRecord, setSavingRecord] = React.useState(false);
  const [savingMetric, setSavingMetric] = React.useState(false);
  const [savingOverride, setSavingOverride] = React.useState(false);
  const [recordForm, setRecordForm] = React.useState({
    scope: "Scope 1",
    activity_date: "2024-07-15",
    source_name: "",
    activity_category: "General",
    quantity: "1000",
    unit: "",
    location: "Central Steel Plant",
  });
  const [metricForm, setMetricForm] = React.useState({
    metric_date: "2024-12-31",
    metric_name: "Tons of Steel Produced",
    value: "50000",
    unit: "tonnes",
  });
  const [overrideForm, setOverrideForm] = React.useState({
    record_id: "",
    new_emissions_kgco2e: "",
    reason: "Corrected meter reading after invoice reconciliation",
    changed_by: "admin@demo.com",
  });

  const activeFactors = React.useMemo(
    () => factors.filter((factor) => factor.scope === recordForm.scope),
    [factors, recordForm.scope],
  );

  async function loadData() {
    setLoading(true);
    const [summaryResponse, factorsResponse, recordsResponse, auditResponse] = await Promise.all([
      fetch(`${API_BASE}/analytics/summary`),
      fetch(`${API_BASE}/metadata/factors?active_on=2024-07-01`),
      fetch(`${API_BASE}/emission-records?limit=8`),
      fetch(`${API_BASE}/audit-logs?limit=6`),
    ]);
    setSummary(await summaryResponse.json());
    const factorPayload: Factor[] = await factorsResponse.json();
    setFactors(factorPayload);
    const recordPayload: EmissionRecord[] = await recordsResponse.json();
    setRecords(recordPayload);
    setAuditLogs(await auditResponse.json());
    if (!overrideForm.record_id && recordPayload.length) {
      const firstRecord = recordPayload[0];
      setOverrideForm((current) => ({
        ...current,
        record_id: String(firstRecord.id),
        new_emissions_kgco2e: String(Math.round(firstRecord.final_emissions_kgco2e * 0.98)),
      }));
    }
    setLoading(false);
  }

  async function loadIntelligence() {
    setIntelligenceLoading(true);
    try {
      const [insightResponse, anomalyResponse, netZeroResponse] = await Promise.all([
        fetch(`${API_BASE}/analytics/ai-insights`),
        fetch(`${API_BASE}/analytics/anomalies?year=2024`),
        fetch(`${API_BASE}/analytics/net-zero?current_year=2024`),
      ]);
      if (!insightResponse.ok || !anomalyResponse.ok || !netZeroResponse.ok) {
        throw new Error("Advanced analytics request failed");
      }
      setInsightPayload(await insightResponse.json());
      setAnomalyPayload(await anomalyResponse.json());
      setNetZeroPayload(await netZeroResponse.json());
    } catch {
      setMessage("Advanced insights are temporarily unavailable. Core reporting remains active.");
    } finally {
      setIntelligenceLoading(false);
    }
  }

  React.useEffect(() => {
    if (initialLoadStarted.current) {
      return;
    }
    initialLoadStarted.current = true;
    loadData().catch(() => {
      setMessage("Backend is not reachable yet. Start Docker Compose or the FastAPI server.");
      setLoading(false);
    });
    loadIntelligence();
  }, []);

  React.useEffect(() => {
    const selected = activeFactors[0];
    if (selected && (!recordForm.source_name || selected.scope !== recordForm.scope)) {
      setRecordForm((current) => ({
        ...current,
        source_name: selected.source_name,
        activity_category: selected.activity_category,
        unit: selected.unit,
      }));
    }
  }, [activeFactors, recordForm.scope]);

  async function submitRecord(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingRecord(true);
    setRecordMessage("");
    try {
      const endpoint = recordForm.scope === "Scope 1" ? "scope-1" : "scope-2";
      const response = await fetch(`${API_BASE}/emission-records/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          activity_date: recordForm.activity_date,
          source_name: recordForm.source_name,
          activity_category: recordForm.activity_category,
          quantity: Number(recordForm.quantity),
          unit: recordForm.unit,
          location: recordForm.location,
          notes: "Created from dashboard form",
        }),
      });
      if (!response.ok) {
        const error = await response.json();
        setRecordMessage(readApiError(error, "Unable to create emission record."));
        return;
      }
      setRecordMessage("Record saved. Emissions were calculated with the date-valid factor.");
      await loadData();
    } catch {
      setRecordMessage("Could not reach the API. Confirm that the backend is running on port 8000.");
    } finally {
      setSavingRecord(false);
    }
  }

  async function submitMetric(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingMetric(true);
    setMetricMessage("");
    try {
      const response = await fetch(`${API_BASE}/business-metrics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metric_date: metricForm.metric_date,
          metric_name: metricForm.metric_name,
          value: Number(metricForm.value),
          unit: metricForm.unit,
        }),
      });
      if (!response.ok) {
        const error = await response.json();
        setMetricMessage(readApiError(error, "Unable to save the business metric."));
        return;
      }
      setMetricMessage("Business metric saved. The intensity KPI has been refreshed.");
      await loadData();
    } catch {
      setMetricMessage("Could not reach the API. Confirm that the backend is running on port 8000.");
    } finally {
      setSavingMetric(false);
    }
  }

  async function submitOverride(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingOverride(true);
    setOverrideMessage("");
    try {
      const response = await fetch(`${API_BASE}/emission-records/${overrideForm.record_id}/override`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          new_emissions_kgco2e: Number(overrideForm.new_emissions_kgco2e),
          reason: overrideForm.reason,
          changed_by: overrideForm.changed_by,
        }),
      });
      if (!response.ok) {
        const error = await response.json();
        setOverrideMessage(readApiError(error, "Unable to apply override."));
        return;
      }
      setOverrideMessage("Override saved. The audit trail now includes this change.");
      await loadData();
    } catch {
      setOverrideMessage("Could not reach the API. Confirm that the backend is running on port 8000.");
    } finally {
      setSavingOverride(false);
    }
  }

  const yoyChart = summary
    ? [
        {
          year: String(summary.yoy.previous_year.year),
          "Scope 1": summary.yoy.previous_year.scope_1_kgco2e / 1000,
          "Scope 2": summary.yoy.previous_year.scope_2_kgco2e / 1000,
        },
        {
          year: String(summary.yoy.selected_year.year),
          "Scope 1": summary.yoy.selected_year.scope_1_kgco2e / 1000,
          "Scope 2": summary.yoy.selected_year.scope_2_kgco2e / 1000,
        },
      ]
    : [];

  const trend = summary
    ? summary.monthly_trend.map((row) => ({
        month: row.month.slice(5),
        "Scope 1": row.scope_1_kgco2e / 1000,
        "Scope 2": row.scope_2_kgco2e / 1000,
        Total: row.total_kgco2e / 1000,
      }))
    : [];

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">GHG Protocol Reporting Platform</p>
          <h1>CarbonSight</h1>
        </div>
        <button
          className="iconButton"
          onClick={() => {
            loadData();
            loadIntelligence();
          }}
          title="Refresh dashboard"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </header>

      {message && <div className="notice">{message}</div>}
      {loading && <div className="notice">Loading emissions analytics...</div>}

      <section className="intelligenceGrid">
        <Panel title="AI Narrative Insights" className="insightPanel">
          <div className="panelHeading">
            <Sparkles size={20} />
            <span>
              {insightPayload?.generated_by === "anthropic"
                ? `Generated by ${insightPayload.model}`
                : "Verified analytics narrative"}
            </span>
          </div>
          {intelligenceLoading && <p className="emptyState">Generating analytical narrative...</p>}
          <ul className="insightList">
            {insightPayload?.insights.map((insight) => <li key={insight}>{insight}</li>)}
          </ul>
          {insightPayload?.notice && <p className="sourceNote">{insightPayload.notice}</p>}
        </Panel>

        <Panel title="Emission Anomalies">
          <div className="panelHeading warningHeading">
            <AlertTriangle size={20} />
            <strong>{anomalyPayload?.total_flagged ?? 0} flagged</strong>
          </div>
          <div className="anomalyList">
            {anomalyPayload?.anomalies.slice(0, 3).map((anomaly) => (
              <div className="anomalyRow" key={anomaly.record_id}>
                <div>
                  <strong>{anomaly.source_name}</strong>
                  <span>
                    Record #{anomaly.record_id} · {anomaly.activity_date}
                  </span>
                </div>
                <span className={`severityBadge ${anomaly.severity}`}>
                  {anomaly.severity} · z {anomaly.z_score.toFixed(2)}
                </span>
              </div>
            ))}
            {!intelligenceLoading && anomalyPayload?.total_flagged === 0 && (
              <p className="emptyState">No source-level statistical outliers detected.</p>
            )}
          </div>
        </Panel>

        <Panel title="2030 Reduction Target">
          <div className="panelHeading">
            <Target size={20} />
            <strong>{netZeroPayload?.progress_pct.toFixed(1) ?? "0.0"}% progress</strong>
          </div>
          <div className="progressTrack" aria-label="Net-zero target progress">
            <span style={{ width: `${netZeroPayload?.progress_pct ?? 0}%` }} />
          </div>
          <div className="targetStats">
            <div>
              <span>Target reduction</span>
              <strong>{netZeroPayload?.target_reduction_pct ?? 50}%</strong>
            </div>
            <div>
              <span>Gap to target</span>
              <strong>{tonnes(netZeroPayload?.gap_to_target_kgco2e ?? 0)}</strong>
            </div>
          </div>
          <p className="sourceNote">
            Baseline {netZeroPayload?.baseline_year ?? 2023} · Target {netZeroPayload?.target_year ?? 2030}
          </p>
        </Panel>
      </section>

      {summary && (
        <>
          <section className="kpiGrid">
            <KpiCard
              icon={<Factory size={20} />}
              label="2024 Scope 1 + 2"
              value={tonnes(summary.yoy.selected_year.total_kgco2e)}
              sublabel="Calculated from seeded activity records"
            />
            <KpiCard
              icon={<Activity size={20} />}
              label="Emission Intensity"
              value={
                summary.intensity.intensity_kgco2e_per_unit
                  ? `${summary.intensity.intensity_kgco2e_per_unit.toLocaleString(undefined, {
                      maximumFractionDigits: 1,
                    })} kg/unit`
                  : "No metric"
              }
              sublabel={summary.intensity.metric_name}
            />
            <KpiCard
              icon={<Database size={20} />}
              label="Metric Denominator"
              value={compactKg(summary.intensity.business_metric_value)}
              sublabel="Tons of steel produced"
            />
            <KpiCard
              icon={<ShieldCheck size={20} />}
              label="Factor Logic"
              value="Date-valid"
              sublabel="Expired and active factor versions are seeded"
            />
          </section>

          <section className="dashboardGrid">
            <Panel title="YoY Emissions by Scope" className="wide">
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={yoyChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dde5e2" />
                  <XAxis dataKey="year" />
                  <YAxis tickFormatter={(value) => `${value / 1000}k`} />
                  <Tooltip formatter={(value) => `${Number(value).toLocaleString()} tCO2e`} />
                  <Legend />
                  <Bar
                    dataKey="Scope 1"
                    stackId="a"
                    fill="#167c80"
                    radius={[4, 4, 0, 0]}
                    isAnimationActive={false}
                  />
                  <Bar
                    dataKey="Scope 2"
                    stackId="a"
                    fill="#d08b30"
                    radius={[4, 4, 0, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </Panel>

            <Panel title="Emission Hotspots">
              <ResponsiveContainer width="100%" height={320}>
                <PieChart>
                  <Pie
                    data={summary.hotspots}
                    dataKey="emissions_kgco2e"
                    nameKey="source_name"
                    innerRadius={72}
                    outerRadius={112}
                    paddingAngle={2}
                    isAnimationActive={false}
                  >
                    {summary.hotspots.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => tonnes(Number(value))} />
                  <Legend layout="vertical" verticalAlign="middle" align="right" />
                </PieChart>
              </ResponsiveContainer>
            </Panel>

            <Panel title="Monthly Emissions Trend" className="wide">
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dde5e2" />
                  <XAxis dataKey="month" />
                  <YAxis tickFormatter={(value) => `${value / 1000}k`} />
                  <Tooltip formatter={(value) => `${Number(value).toLocaleString()} tCO2e`} />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="Total"
                    stroke="#294c60"
                    strokeWidth={3}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="Scope 1"
                    stroke="#167c80"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="Scope 2"
                    stroke="#d08b30"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </Panel>

            <Panel title="Top Sources">
              <div className="hotspotList">
                {summary.hotspots.map((item) => (
                  <div className="hotspotRow" key={`${item.scope}-${item.source_name}`}>
                    <div>
                      <strong>{item.source_name}</strong>
                      <span>{item.scope}</span>
                    </div>
                    <div>
                      <strong>{tonnes(item.emissions_kgco2e)}</strong>
                      <span>{item.share_pct.toFixed(1)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </section>
        </>
      )}

      <section className="formGrid">
        <Panel title="Create Emission Record">
          <form onSubmit={submitRecord}>
            <label>
              Scope
              <select
                value={recordForm.scope}
                onChange={(event) => setRecordForm({ ...recordForm, scope: event.target.value, source_name: "" })}
              >
                <option>Scope 1</option>
                <option>Scope 2</option>
              </select>
            </label>
            <label>
              Activity date
              <input
                type="date"
                value={recordForm.activity_date}
                onChange={(event) => setRecordForm({ ...recordForm, activity_date: event.target.value })}
              />
            </label>
            <label>
              Source
              <select
                value={recordForm.source_name}
                onChange={(event) => {
                  const selected = factors.find(
                    (factor) => factor.scope === recordForm.scope && factor.source_name === event.target.value,
                  );
                  setRecordForm({
                    ...recordForm,
                    source_name: event.target.value,
                    activity_category: selected?.activity_category ?? recordForm.activity_category,
                    unit: selected?.unit ?? recordForm.unit,
                  });
                }}
              >
                {activeFactors.map((factor) => (
                  <option key={factor.id} value={factor.source_name}>
                    {factor.source_name} ({factor.unit})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Quantity
              <input
                type="number"
                min="0"
                step="0.01"
                value={recordForm.quantity}
                onChange={(event) => setRecordForm({ ...recordForm, quantity: event.target.value })}
              />
            </label>
            <label>
              Unit
              <input
                value={recordForm.unit}
                onChange={(event) => setRecordForm({ ...recordForm, unit: event.target.value })}
              />
            </label>
            <button className="primaryButton" type="submit" disabled={savingRecord}>
              <Save size={17} />
              {savingRecord ? "Saving..." : "Save record"}
            </button>
            <InlineStatus message={recordMessage} />
          </form>
        </Panel>

        <Panel title="Add Business Metric">
          <form onSubmit={submitMetric}>
            <label>
              Metric date
              <input
                type="date"
                value={metricForm.metric_date}
                onChange={(event) => setMetricForm({ ...metricForm, metric_date: event.target.value })}
              />
            </label>
            <label>
              Metric name
              <input
                value={metricForm.metric_name}
                onChange={(event) => setMetricForm({ ...metricForm, metric_name: event.target.value })}
              />
            </label>
            <label>
              Value
              <input
                type="number"
                min="0"
                step="0.01"
                value={metricForm.value}
                onChange={(event) => setMetricForm({ ...metricForm, value: event.target.value })}
              />
            </label>
            <label>
              Unit
              <input value={metricForm.unit} onChange={(event) => setMetricForm({ ...metricForm, unit: event.target.value })} />
            </label>
            <button className="primaryButton" type="submit" disabled={savingMetric}>
              <Save size={17} />
              {savingMetric ? "Saving..." : "Save metric"}
            </button>
            <InlineStatus message={metricMessage} />
          </form>
        </Panel>
      </section>

      <section className="auditGrid">
        <Panel title="Manual Override">
          <form onSubmit={submitOverride}>
            <label>
              Record
              <select
                value={overrideForm.record_id}
                onChange={(event) => {
                  const selected = records.find((record) => String(record.id) === event.target.value);
                  setOverrideForm({
                    ...overrideForm,
                    record_id: event.target.value,
                    new_emissions_kgco2e: selected ? String(Math.round(selected.final_emissions_kgco2e * 0.98)) : "",
                  });
                }}
              >
                {records.map((record) => (
                  <option key={record.id} value={record.id}>
                    #{record.id} {record.scope} - {record.source_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              New kgCO2e
              <input
                type="number"
                min="0"
                step="0.01"
                value={overrideForm.new_emissions_kgco2e}
                onChange={(event) => setOverrideForm({ ...overrideForm, new_emissions_kgco2e: event.target.value })}
              />
            </label>
            <label>
              Reason
              <input
                value={overrideForm.reason}
                onChange={(event) => setOverrideForm({ ...overrideForm, reason: event.target.value })}
              />
            </label>
            <label>
              Changed by
              <input
                value={overrideForm.changed_by}
                onChange={(event) => setOverrideForm({ ...overrideForm, changed_by: event.target.value })}
              />
            </label>
            <button className="primaryButton" type="submit" disabled={savingOverride}>
              <ShieldCheck size={17} />
              {savingOverride ? "Saving..." : "Apply override"}
            </button>
            <InlineStatus message={overrideMessage} />
          </form>
        </Panel>

        <Panel title="Audit Trail">
          <div className="auditList">
            {auditLogs.length === 0 && <p className="emptyState">No overrides recorded yet.</p>}
            {auditLogs.map((log) => (
              <div className="auditRow" key={log.id}>
                <div>
                  <strong>Record #{log.record_id}</strong>
                  <span>{log.changed_by}</span>
                  <p>{log.reason}</p>
                </div>
                <div>
                  <strong>{tonnes(log.new_value)}</strong>
                  <span>was {tonnes(log.old_value)}</span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </section>
    </main>
  );
}

function KpiCard({
  icon,
  label,
  value,
  sublabel,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sublabel: string;
}) {
  return (
    <article className="kpiCard">
      <div className="kpiIcon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <p>{sublabel}</p>
      </div>
    </article>
  );
}

function Panel({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function InlineStatus({ message }: { message: string }) {
  if (!message) {
    return null;
  }
  return (
    <p className="inlineStatus" role="status" aria-live="polite">
      {message}
    </p>
  );
}

function readApiError(error: { detail?: string; errors?: { message: string }[] }, fallback: string) {
  if (error.errors?.length) {
    return error.errors.map((item) => item.message).join(" ");
  }
  return error.detail ?? fallback;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
