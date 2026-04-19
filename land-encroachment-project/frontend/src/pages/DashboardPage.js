import Badge from "../components/Badge";
import Card from "../components/Card";
import {
  ROLE_CONFIG,
  getLocalizedText,
  getRoleInsights,
} from "../config/appContent";
import { COLORS } from "../theme/colors";

export default function DashboardPage({ alerts, auth, loadError, loading, plots }) {
  const highRisk = plots.filter((plot) => plot.risk === "High").length;
  const mediumRisk = plots.filter((plot) => plot.risk === "Medium").length;
  const lowRisk = plots.filter(
    (plot) => plot.risk === "Low" || plot.risk === "Suspicious"
  ).length;
  const escalatedToday = alerts.filter((alert) => alert.risk === "High").length;

  const cards = [
    { label: "Total Plots", value: loading ? "..." : plots.length, color: COLORS.primary },
    { label: "High Risk", value: loading ? "..." : highRisk, color: COLORS.riskHigh },
    { label: "Medium Risk", value: loading ? "..." : mediumRisk, color: COLORS.riskMedium },
    { label: "Public / Watch", value: loading ? "..." : lowRisk, color: COLORS.riskLow },
  ];

  const roleInsights = getRoleInsights(auth.role, plots, alerts);

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div>
          <p className="section-eyebrow">
            {getLocalizedText(auth.language, "Overview", "Overview")}
          </p>
          <h1 className="page-title">Chennai land risk dashboard</h1>
          {loadError ? <p className="status-error">{loadError}</p> : null}
        </div>

        <div className="hero-summary">
          <span>Mode</span>
          <strong>{ROLE_CONFIG[auth.role]?.label || auth.role}</strong>
          <Badge tone="info">Chennai Command View</Badge>
        </div>
      </section>

      <section className="kpi-grid">
        {cards.map((card) => (
          <Card className="kpi-card" key={card.label}>
            <div className="kpi-header">
              <span
                className="kpi-icon"
                style={{
                  backgroundColor: `${card.color}14`,
                  color: card.color,
                }}
              >
                {card.value}
              </span>
            </div>
            <p className="kpi-label">{card.label}</p>
            <strong className="kpi-value">{card.value}</strong>
          </Card>
        ))}
      </section>

      <section className="overview-grid">
        <Card eyebrow="Operational Brief" title="Monitoring summary">
          <div className="summary-list">
            <div className="summary-row">
              <span>Total alerts in system</span>
              <strong>{alerts.length}</strong>
            </div>
            <div className="summary-row">
              <span>Plots requiring escalation</span>
              <strong>{highRisk}</strong>
            </div>
            <div className="summary-row">
              <span>Escalated cases</span>
              <strong>{escalatedToday}</strong>
            </div>
          </div>
        </Card>

        <Card eyebrow="Industry Features" title="Response intelligence">
          <div className="response-intelligence-grid">
            {roleInsights.map((item) => (
              <div className="response-intelligence-card" key={item.label}>
                <Badge tone={item.tone}>{item.value}</Badge>
                <strong>{item.label}</strong>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </div>
  );
}
