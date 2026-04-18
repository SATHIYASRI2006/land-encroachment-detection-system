import Card from "../components/Card";
import { getLocalizedText } from "../config/appContent";
import { COLORS } from "../theme/colors";

function getRiskTotals(plots) {
  return plots.reduce(
    (totals, plot) => {
      totals[plot.risk] = (totals[plot.risk] || 0) + 1;
      return totals;
    },
    { High: 0, Medium: 0, Suspicious: 0, Low: 0 }
  );
}

function buildTrendSeries(plots) {
  return plots
    .slice()
    .sort((left, right) => Number(right.change || 0) - Number(left.change || 0))
    .slice(0, 6)
    .map((plot) => Number(plot.change || 0));
}

function linePath(values, width, height) {
  if (!values.length) {
    return "";
  }
  const maxValue = Math.max(...values, 1);
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - (value / maxValue) * height;
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
}

export default function AnalyticsPage({ auth, plots, alerts, loading }) {
  const riskTotals = getRiskTotals(plots);
  const trendSeries = buildTrendSeries(plots);
  const areaStats = plots.reduce((acc, plot) => {
    if (!acc[plot.area]) {
      acc[plot.area] = {
        area: plot.area,
        totalPlots: 0,
        highRisk: 0,
        mediumRisk: 0,
        avgChange: 0,
      };
    }

    acc[plot.area].totalPlots += 1;
    acc[plot.area].highRisk += plot.risk === "High" ? 1 : 0;
    acc[plot.area].mediumRisk += plot.risk === "Medium" ? 1 : 0;
    acc[plot.area].avgChange += Number(plot.change || 0);
    return acc;
  }, {});

  const rows = Object.values(areaStats).map((item) => ({
    ...item,
    avgChange: item.totalPlots
      ? (item.avgChange / item.totalPlots).toFixed(2)
      : "0.00",
  }));

  const riskBars = [
    { label: "High", value: riskTotals.High, color: COLORS.riskHigh },
    { label: "Medium", value: riskTotals.Medium, color: COLORS.riskMedium },
    { label: "Watch", value: riskTotals.Low + riskTotals.Suspicious, color: COLORS.riskLow },
  ];
  const maxRiskBar = Math.max(...riskBars.map((item) => item.value), 1);
  const riskScore = Math.round(
    ((riskTotals.High * 3 + riskTotals.Medium * 2 + (riskTotals.Low + riskTotals.Suspicious)) /
      Math.max(plots.length * 3, 1)) *
      100
  );

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <p className="section-eyebrow">
            {getLocalizedText(auth.language, "Analytics", "Analytics")}
          </p>
          <h1 className="page-title">Analytics and trends</h1>
          <p className="body-copy">
            Live analytics are now generated from the actual plot and alert data instead of static placeholders.
          </p>
        </div>
      </section>

      <section className="kpi-grid">
        <Card className="kpi-card">
          <p className="kpi-label">High Risk</p>
          <strong className="kpi-value">{loading ? "..." : riskTotals.High}</strong>
        </Card>
        <Card className="kpi-card">
          <p className="kpi-label">Medium Risk</p>
          <strong className="kpi-value">{loading ? "..." : riskTotals.Medium}</strong>
        </Card>
        <Card className="kpi-card">
          <p className="kpi-label">Low / Watch</p>
          <strong className="kpi-value">
            {loading ? "..." : riskTotals.Low + riskTotals.Suspicious}
          </strong>
        </Card>
        <Card className="kpi-card">
          <p className="kpi-label">Open Alerts</p>
          <strong className="kpi-value">{loading ? "..." : alerts.length}</strong>
        </Card>
      </section>

      <section className="analytics-grid">
        <Card eyebrow="Risk Matrix" title="Dynamic risk distribution">
          <div className="dynamic-chart-card">
            <div className="dynamic-bar-grid">
              {riskBars.map((bar) => (
                <div className="dynamic-bar-column" key={bar.label}>
                  <div className="dynamic-bar-track">
                    <div
                      className="dynamic-bar-fill"
                      style={{
                        height: `${Math.max((bar.value / maxRiskBar) * 100, 12)}%`,
                        background: `linear-gradient(180deg, ${bar.color}, ${bar.color}CC)`,
                      }}
                    />
                  </div>
                  <strong>{bar.value}</strong>
                  <span>{bar.label}</span>
                </div>
              ))}
            </div>
            <div className="dynamic-chart-summary">
              <span>Composite risk load</span>
              <strong>{riskScore}%</strong>
            </div>
          </div>
        </Card>

        <Card eyebrow="Operational Trend" title="Observed change intensity">
          <div className="dynamic-chart-card">
            <svg className="trend-svg" viewBox="0 0 320 160" role="img" aria-label="Change trend">
              <defs>
                <linearGradient id="trendStroke" x1="0%" x2="100%" y1="0%" y2="0%">
                  <stop offset="0%" stopColor={COLORS.secondary} />
                  <stop offset="100%" stopColor={COLORS.primary} />
                </linearGradient>
              </defs>
              <path
                d={linePath(trendSeries, 300, 120)}
                fill="none"
                stroke="url(#trendStroke)"
                strokeWidth="8"
                strokeLinecap="round"
                transform="translate(10 20)"
              />
            </svg>
            <div className="summary-list">
              <div className="summary-row">
                <span>Highest observed change</span>
                <strong>{plots.length ? `${Math.max(...trendSeries, 0).toFixed(2)}%` : "0.00%"}</strong>
              </div>
              <div className="summary-row">
                <span>Average parcel confidence</span>
                <strong>
                  {plots.length
                    ? `${(
                        plots.reduce((sum, plot) => sum + Number(plot.confidence || 0), 0) /
                        plots.length
                      ).toFixed(2)}%`
                    : "0.00%"}
                </strong>
              </div>
            </div>
          </div>
        </Card>
      </section>

      <Card eyebrow="Area Report" title="Encroachment by Chennai area">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Area</th>
                <th>Total Plots</th>
                <th>High Risk</th>
                <th>Medium Risk</th>
                <th>Average Change</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.area}>
                  <td>{row.area}</td>
                  <td>{row.totalPlots}</td>
                  <td>{row.highRisk}</td>
                  <td>{row.mediumRisk}</td>
                  <td>{row.avgChange}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
