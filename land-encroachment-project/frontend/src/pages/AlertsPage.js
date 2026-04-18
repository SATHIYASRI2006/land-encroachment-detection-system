import Badge from "../components/Badge";
import Card from "../components/Card";
import { getLocalizedText } from "../config/appContent";

function formatDate(value) {
  return new Date(value).toLocaleString();
}

export default function AlertsPage({ alerts, auth, plots, loading }) {
  const publicAlerts =
    auth.role === "viewer" ? alerts.filter((alert) => alert.risk !== "High") : alerts;

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <p className="section-eyebrow">
            {getLocalizedText(auth.language, "Alerts", "எச்சரிக்கைகள்")}
          </p>
          <h1 className="page-title">
            {getLocalizedText(auth.language, "Alert monitoring desk", "எச்சரிக்கை கண்காணிப்பு மையம்")}
          </h1>
          <p className="body-copy">
            {auth.role === "viewer"
              ? getLocalizedText(
                  auth.language,
                  "Citizens see verified public-safe updates only.",
                  "பொது மக்களுக்கு பாதுகாப்பான மற்றும் சரிபார்க்கப்பட்ட தகவல்கள் மட்டும் காட்டப்படும்."
                )
              : getLocalizedText(
                  auth.language,
                  "Officials and admins can review incident severity, timing, and operational status.",
                  "அதிகாரிகள் மற்றும் நிர்வாகிகள் சம்பவ தீவிரம், நேரம், மற்றும் செயல்நிலையை பார்க்கலாம்."
                )}
          </p>
        </div>
      </section>

      <section className="kpi-grid kpi-grid-compact">
        <Card className="kpi-card">
          <p className="kpi-label">{getLocalizedText(auth.language, "Alert Feed", "எச்சரிக்கை தொகுப்பு")}</p>
          <strong className="kpi-value">{loading ? "..." : publicAlerts.length}</strong>
        </Card>
        <Card className="kpi-card">
          <p className="kpi-label">{getLocalizedText(auth.language, "Plots Monitored", "கண்காணிப்பு நிலங்கள்")}</p>
          <strong className="kpi-value">{loading ? "..." : plots.length}</strong>
        </Card>
        <Card className="kpi-card">
          <p className="kpi-label">{getLocalizedText(auth.language, "Delivery", "விநியோகம்")}</p>
          <strong className="kpi-value">
            {auth.role === "viewer" ? "Public Desk" : "Mail + UI"}
          </strong>
        </Card>
      </section>

      <Card
        eyebrow={getLocalizedText(auth.language, "Alert Register", "எச்சரிக்கை பதிவு")}
        title={getLocalizedText(auth.language, "Incident table", "சம்பவ அட்டவணை")}
      >
        {publicAlerts.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{getLocalizedText(auth.language, "Place", "இடம்")}</th>
                  <th>{getLocalizedText(auth.language, "Risk Level", "ஆபத்து நிலை")}</th>
                  <th>{getLocalizedText(auth.language, "Time", "நேரம்")}</th>
                  <th>{getLocalizedText(auth.language, "Status", "நிலை")}</th>
                </tr>
              </thead>
              <tbody>
                {publicAlerts.map((alert) => (
                  <tr key={alert.id}>
                    <td>{alert.plotName}</td>
                    <td>
                      <Badge tone={alert.risk.toLowerCase()}>{alert.risk}</Badge>
                    </td>
                    <td>{formatDate(alert.receivedAt)}</td>
                    <td>
                      <Badge tone={alert.isRead ? "low" : "warning"}>
                        {auth.role === "viewer"
                          ? getLocalizedText(auth.language, "Verified", "சரிபார்க்கப்பட்டது")
                          : alert.isRead
                            ? "Read"
                            : "Active"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted-text">
            {getLocalizedText(
              auth.language,
              "No alerts are available yet. New incidents will appear here as they are received.",
              "இப்போது எச்சரிக்கைகள் இல்லை. புதிய தகவல்கள் வந்தவுடன் இங்கு காட்டப்படும்."
            )}
          </p>
        )}
      </Card>
    </div>
  );
}
