import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api.js";
import { CATEGORY_COLORS, compact, currentMonth, longMonth, money, monthLabel, shiftMonth } from "../format.js";

export default function Dashboard() {
  const [month, setMonth] = useState(currentMonth());
  const [summary, setSummary] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [budgets, setBudgets] = useState([]);
  const [error, setError] = useState("");
  const [loadingDemo, setLoadingDemo] = useState(false);

  const load = useCallback(() => {
    setError("");
    Promise.all([api.summary(month), api.forecast(3), api.budgets(month)])
      .then(([s, f, b]) => {
        setSummary(s);
        setForecast(f);
        setBudgets(b);
      })
      .catch((e) => setError(e.message));
  }, [month]);

  useEffect(load, [load]);

  async function loadDemo() {
    setLoadingDemo(true);
    try {
      await api.loadDemo(false);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingDemo(false);
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!summary || !forecast) return <p className="muted">Loading...</p>;

  const noData = forecast.months_of_history === 0 && summary.transactions === 0;
  if (noData) {
    return (
      <div className="empty card">
        <h2>No expenses yet</h2>
        <p className="muted">
          Add your first expense, import a CSV, or load 18 months of realistic sample data to explore the dashboard.
        </p>
        <div className="row">
          <Link to="/expenses" className="btn primary">Add an expense</Link>
          <button className="btn" onClick={loadDemo} disabled={loadingDemo}>
            {loadingDemo ? "Loading..." : "Load sample data"}
          </button>
        </div>
      </div>
    );
  }

  const isCurrent = month === currentMonth();
  // forecast[0] is the current (incomplete) month; the card shows the month after it
  const next = forecast.forecast[1] || forecast.forecast[0];
  const projection = forecast.current_month;

  const chartData = [
    ...forecast.history.map((h) => ({ month: monthLabel(h.month), actual: h.total })),
    ...forecast.forecast.map((f) => ({
      month: monthLabel(f.month),
      predicted: f.predicted,
      range: [f.lower, f.upper],
    })),
  ];
  // connect the forecast line to the last actual point
  if (forecast.history.length && forecast.forecast.length) {
    const lastActual = chartData[forecast.history.length - 1];
    lastActual.predicted = lastActual.actual;
    lastActual.range = [lastActual.actual, lastActual.actual];
  }

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>{longMonth(month)}</h1>
          <p className="muted">{summary.transactions} transactions</p>
        </div>
        <div className="month-switch">
          <button className="btn small" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">‹</button>
          <button className="btn small" onClick={() => setMonth(currentMonth())} disabled={isCurrent}>This month</button>
          <button className="btn small" onClick={() => setMonth(shiftMonth(month, 1))} disabled={isCurrent} aria-label="Next month">›</button>
        </div>
      </div>

      <section className="kpis">
        <Kpi
          label={isCurrent ? "Spent so far" : "Total spent"}
          value={money(summary.total)}
          note={
            summary.change_percent == null
              ? "No data for previous month"
              : `${summary.change_percent > 0 ? "+" : ""}${summary.change_percent}% vs ${monthLabel(shiftMonth(month, -1))}`
          }
          tone={summary.change_percent > 0 ? "up" : "down"}
        />
        <Kpi label="Average per day" value={money(summary.average_daily)} note={`${summary.daily.length} days counted`} />
        {isCurrent && projection && (
          <Kpi
            label="Projected month end"
            value={money(projection.projected_total)}
            note={`Day ${projection.days_elapsed} of ${projection.days_in_month}`}
          />
        )}
        {next && (
          <Kpi
            label={`Forecast for ${monthLabel(next.month)}`}
            value={money(next.predicted)}
            note={`Likely ${compact(next.lower)} to ${compact(next.upper)}`}
            highlight
          />
        )}
      </section>

      <section className="grid two">
        <div className="card wide">
          <div className="card-head">
            <h2>Monthly spending and forecast</h2>
            <span className="muted small-text">{forecast.method}</span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: "var(--muted)" }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={compact} tick={{ fontSize: 12, fill: "var(--muted)" }} tickLine={false} axisLine={false} width={44} />
              <Tooltip content={<ForecastTooltip />} />
              <Area dataKey="range" stroke="none" fill="var(--accent)" fillOpacity={0.15} name="80% range" />
              <Bar dataKey="actual" fill="var(--ink-soft)" radius={[2, 2, 0, 0]} name="Actual" maxBarSize={28} />
              <Line dataKey="predicted" stroke="var(--accent)" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3 }} name="Forecast" />
            </ComposedChart>
          </ResponsiveContainer>
          <div className="legend">
            <span><i className="swatch ink" /> Actual</span>
            <span><i className="swatch accent dashed" /> Forecast</span>
            <span><i className="swatch band" /> Likely range (80%)</span>
          </div>
        </div>

        <div className="card">
          <h2>Where it went</h2>
          {summary.by_category.length === 0 ? (
            <p className="muted">No expenses this month.</p>
          ) : (
            <div className="donut">
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={summary.by_category} dataKey="amount" nameKey="category" innerRadius={55} outerRadius={85} paddingAngle={1} stroke="none">
                    {summary.by_category.map((c) => <Cell key={c.category} fill={CATEGORY_COLORS[c.category]} />)}
                  </Pie>
                  <Tooltip formatter={(v) => money(v)} />
                </PieChart>
              </ResponsiveContainer>
              <ul className="category-list">
                {summary.by_category.map((c) => (
                  <li key={c.category}>
                    <i className="dot" style={{ background: CATEGORY_COLORS[c.category] }} />
                    <span>{c.category}</span>
                    <span className="muted">{Math.round(c.share * 100)}%</span>
                    <strong>{money(c.amount)}</strong>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="card">
          <h2>Insights</h2>
          {forecast.insights.length ? (
            <ul className="insights">
              {forecast.insights.map((tip) => <li key={tip}>{tip}</li>)}
            </ul>
          ) : (
            <p className="muted">Nothing unusual this month.</p>
          )}
          <h3>Next month by category</h3>
          <table className="mini-table">
            <tbody>
              {forecast.next_month_by_category.slice(0, 6).map((c) => (
                <tr key={c.category}>
                  <td>{c.category}</td>
                  <td className={`trend ${c.trend}`}>{c.trend === "up" ? "▲" : c.trend === "down" ? "▼" : "–"}</td>
                  <td className="num">{money(c.predicted)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2>Daily spending</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={summary.daily.map((d) => ({ day: Number(d.date.slice(8)), amount: d.amount }))}>
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={false} interval={4} />
              <YAxis tickFormatter={compact} tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={false} width={40} />
              <Tooltip formatter={(v) => money(v)} labelFormatter={(d) => `Day ${d}`} />
              <Bar dataKey="amount" fill="var(--ink-soft)" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>Budgets</h2>
            <Link to="/budgets" className="small-text">Manage</Link>
          </div>
          {budgets.length === 0 ? (
            <p className="muted">No budgets set. <Link to="/budgets">Set monthly limits</Link> to get alerts.</p>
          ) : (
            budgets.map((b) => <BudgetBar key={b.category} budget={b} />)
          )}
        </div>

        <div className="card wide">
          <h2>Largest expenses</h2>
          <table className="table">
            <tbody>
              {summary.top_expenses.map((e) => (
                <tr key={e.id}>
                  <td className="muted">{e.date}</td>
                  <td>{e.description || "-"}</td>
                  <td><span className="tag" style={{ borderColor: CATEGORY_COLORS[e.category] }}>{e.category}</span></td>
                  <td className="num"><strong>{money(e.amount)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Kpi({ label, value, note, tone, highlight }) {
  return (
    <div className={`kpi ${highlight ? "highlight" : ""}`}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      {note && <span className={`kpi-note ${tone || ""}`}>{note}</span>}
    </div>
  );
}

export function BudgetBar({ budget, showLabel = true }) {
  const pct = Math.min(100, budget.percent_used);
  return (
    <div className="budget-bar">
      <div className="budget-top">
        <span>{showLabel ? budget.category : `${Math.round(budget.percent_used)}% used`}</span>
        <span className={`status ${budget.status}`}>
          {money(budget.spent)} / {money(budget.monthly_limit)}
        </span>
      </div>
      <div className="track"><span className={budget.status} style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

function ForecastTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="tooltip">
      <strong>{label}</strong>
      {row.actual != null && <div>Actual: {money(row.actual)}</div>}
      {row.actual == null && row.predicted != null && (
        <>
          <div>Forecast: {money(row.predicted)}</div>
          <div className="muted">Range: {money(row.range[0])} to {money(row.range[1])}</div>
        </>
      )}
    </div>
  );
}
