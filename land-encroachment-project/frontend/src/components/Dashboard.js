import { useState } from "react";
import { Link } from "react-router-dom";

import Badge from "./Badge";
import Card from "./Card";
import { getLocalizedText } from "../config/appContent";
import { generatePlotReport, getReportDownloadUrl } from "../services/api";

function formatValue(value, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
  return `${Number(value).toFixed(2)}${suffix}`;
}

export default function Dashboard({ auth, data }) {
  const [reportStatus, setReportStatus] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  if (!data) {
    return (
      <Card eyebrow="Selected Plot" title="No plot selected">
        <p className="muted-text">
          Select a location on the map or from plot details to inspect the
          encroachment summary.
        </p>
      </Card>
    );
  }

  async function handleGenerateReport() {
    try {
      setIsGenerating(true);
      setReportStatus(
        getLocalizedText(auth.language, "Generating report...", "அறிக்கை உருவாக்கப்படுகிறது...")
      );
      const response = await generatePlotReport(data.id);
      const downloadUrl = getReportDownloadUrl(response?.data?.download_url);
      if (downloadUrl) {
        window.open(downloadUrl, "_blank", "noopener,noreferrer");
      }
      setReportStatus(
        getLocalizedText(auth.language, "Report generated successfully.", "அறிக்கை வெற்றிகரமாக உருவாக்கப்பட்டது.")
      );
    } catch (error) {
      setReportStatus(
        error.response?.data?.error?.message ||
          getLocalizedText(auth.language, "Failed to generate report.", "அறிக்கை உருவாக்க முடியவில்லை.")
      );
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleShareReport() {
    try {
      setIsGenerating(true);
      const response = await generatePlotReport(data.id);
      const downloadUrl = getReportDownloadUrl(response?.data?.download_url);
      if (!downloadUrl) {
        throw new Error("Report link unavailable");
      }

      let statusMessage = getLocalizedText(
        auth.language,
        "Report link is ready to share.",
        "அறிக்கை இணைப்பு பகிர தயாராக உள்ளது."
      );

      if (navigator.share) {
        await navigator.share({
          title: `${data.plotName} Report`,
          text: `Land encroachment report for ${data.plotName}`,
          url: downloadUrl,
        });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(downloadUrl);
        statusMessage = getLocalizedText(
          auth.language,
          "Report link copied. You can share it now.",
          "அறிக்கை இணைப்பு நகலெடுக்கப்பட்டது."
        );
      } else {
        window.open(downloadUrl, "_blank", "noopener,noreferrer");
        statusMessage = getLocalizedText(
          auth.language,
          "Report opened in a new tab for sharing.",
          "அறிக்கை புதிய தாளில் திறக்கப்பட்டது."
        );
      }

      setReportStatus(statusMessage);
    } catch (error) {
      setReportStatus(
        error.message ||
          getLocalizedText(auth.language, "Unable to share report.", "அறிக்கையை பகிர முடியவில்லை.")
      );
    } finally {
      setIsGenerating(false);
    }
  }

  const metrics = [
    { label: getLocalizedText(auth.language, "Area", "பகுதி"), value: data.area },
    {
      label: getLocalizedText(auth.language, "Change", "மாற்றம்"),
      value: formatValue(data.change, "%"),
    },
    {
      label: getLocalizedText(auth.language, "Confidence", "நம்பிக்கை அளவு"),
      value: formatValue(data.confidence, "%"),
    },
    {
      label: getLocalizedText(auth.language, "Coordinates", "இருப்பிடம்"),
      value: `${Number(data.lat).toFixed(4)}, ${Number(data.lng).toFixed(4)}`,
    },
  ];

  if (auth.role !== "viewer") {
    metrics.push(
      {
        label: getLocalizedText(auth.language, "Survey No", "சர்வே எண்"),
        value: data.survey_no,
      },
      {
        label: getLocalizedText(auth.language, "Owner", "உரிமையாளர்"),
        value: data.owner_name,
      }
    );
  }

  return (
    <Card
      eyebrow={getLocalizedText(auth.language, "Selected Plot", "தேர்ந்தெடுக்கப்பட்ட நிலம்")}
      title={data.plotName}
      action={<Badge tone={data.risk.toLowerCase()}>{data.risk} Risk</Badge>}
    >
      <div className="plot-summary-grid">
        {metrics.map((item) => (
          <div className="metric-box" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>

      <div className="insight-banner">
        <strong>
          {auth.role === "viewer"
            ? getLocalizedText(auth.language, "Public note", "பொது குறிப்பு")
            : getLocalizedText(auth.language, "Case note", "வழக்கு குறிப்பு")}
        </strong>
        <p className="body-copy">
          {auth.role === "viewer"
            ? getLocalizedText(
                auth.language,
                "This view shares safe public information only. Sensitive ownership and enforcement details are hidden.",
                "இந்த பார்வையில் பொதுமக்களுக்கு தேவையான பாதுகாப்பான தகவல்கள் மட்டும் காட்டப்படுகின்றன."
              )
            : data.operator_note}
        </p>
      </div>

      <div className="report-actions">
        <button disabled={isGenerating} onClick={handleGenerateReport} type="button">
          {isGenerating
            ? getLocalizedText(auth.language, "Generating...", "உருவாக்கப்படுகிறது...")
            : getLocalizedText(auth.language, "Generate Report", "அறிக்கை உருவாக்கு")}
        </button>
        <button className="ghost-button" disabled={isGenerating} onClick={handleShareReport} type="button">
          {getLocalizedText(auth.language, "Share Report", "அறிக்கையை பகிரவும்")}
        </button>
      </div>

      {reportStatus ? <p className="muted-text">{reportStatus}</p> : null}

      <Link className="text-link" to="/plot-details">
        {getLocalizedText(auth.language, "Open full plot register", "முழு நிலப் பதிவை திறக்கவும்")}
      </Link>
    </Card>
  );
}
