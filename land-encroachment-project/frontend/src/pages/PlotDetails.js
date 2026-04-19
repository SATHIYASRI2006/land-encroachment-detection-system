import { useState } from "react";
import { Link } from "react-router-dom";

import { getLocalizedText } from "../config/appContent";
import { generatePlotReport, getReportDownloadUrl } from "../services/api";

export default function PlotDetails({ auth, plots, loading }) {
  const [activePlotId, setActivePlotId] = useState("");
  const [message, setMessage] = useState("");

  async function handleGenerateReport(plot) {
    try {
      setActivePlotId(plot.id);
      setMessage(
        getLocalizedText(auth.language, "Generating report...", "அறிக்கை உருவாக்கப்படுகிறது...")
      );
      const response = await generatePlotReport(plot.id);
      const downloadUrl = getReportDownloadUrl(response?.data?.download_url);
      if (downloadUrl) {
        window.open(downloadUrl, "_blank", "noopener,noreferrer");
      }
      setMessage(
        getLocalizedText(auth.language, "Report generated successfully.", "அறிக்கை வெற்றிகரமாக உருவாக்கப்பட்டது.")
      );
    } catch (error) {
      setMessage(
        error.response?.data?.error?.message ||
          getLocalizedText(auth.language, "Failed to generate report.", "அறிக்கை உருவாக்க முடியவில்லை.")
      );
    } finally {
      setActivePlotId("");
    }
  }

  async function handleShareReport(plot) {
    try {
      setActivePlotId(plot.id);
      const response = await generatePlotReport(plot.id);
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
          title: `${plot.plotName} Report`,
          text: `Land encroachment report for ${plot.plotName}`,
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

      setMessage(statusMessage);
    } catch (error) {
      setMessage(
        error.message ||
          getLocalizedText(auth.language, "Unable to share report.", "அறிக்கையை பகிர முடியவில்லை.")
      );
    } finally {
      setActivePlotId("");
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div>
          <p className="section-eyebrow">
            {getLocalizedText(auth.language, "Plot Details", "நில விவரங்கள்")}
          </p>
          <h1 className="page-title">
            {getLocalizedText(auth.language, "Full plot register", "முழு நிலப் பதிவு")}
          </h1>
          {message ? <p className="muted-text">{message}</p> : null}
        </div>
      </section>

      <section className="ui-card">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>{getLocalizedText(auth.language, "Place", "இடம்")}</th>
                <th>{getLocalizedText(auth.language, "Area", "பகுதி")}</th>
                <th>{getLocalizedText(auth.language, "Risk Level", "ஆபத்து நிலை")}</th>
                <th>{getLocalizedText(auth.language, "Change", "மாற்றம்")}</th>
                <th>{getLocalizedText(auth.language, "Confidence", "நம்பிக்கை")}</th>
                {auth.role !== "viewer" ? <th>Survey</th> : null}
                <th>{getLocalizedText(auth.language, "Latitude", "அட்சரேகை")}</th>
                <th>{getLocalizedText(auth.language, "Longitude", "தேற்றரேகை")}</th>
                <th>{getLocalizedText(auth.language, "Report", "அறிக்கை")}</th>
              </tr>
            </thead>
            <tbody>
              {plots.map((plot) => (
                <tr key={plot.id}>
                  <td>
                    <Link className="text-link" to={`/map?plot=${plot.id}`}>
                      {plot.plotName}
                    </Link>
                  </td>
                  <td>{plot.area}</td>
                  <td>{plot.risk}</td>
                  <td>{plot.change.toFixed(2)}%</td>
                  <td>{plot.confidence.toFixed(2)}%</td>
                  {auth.role !== "viewer" ? <td>{plot.survey_no}</td> : null}
                  <td>{plot.lat.toFixed(4)}</td>
                  <td>{plot.lng.toFixed(4)}</td>
                  <td>
                    <div className="inline-actions">
                      <button
                        disabled={activePlotId === plot.id}
                        onClick={() => handleGenerateReport(plot)}
                        type="button"
                      >
                        {activePlotId === plot.id
                          ? getLocalizedText(auth.language, "Generating...", "உருவாக்கப்படுகிறது...")
                          : getLocalizedText(auth.language, "Generate", "உருவாக்கு")}
                      </button>
                      <button
                        className="ghost-button"
                        disabled={activePlotId === plot.id}
                        onClick={() => handleShareReport(plot)}
                        type="button"
                      >
                        {getLocalizedText(auth.language, "Share", "பகிர்")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!plots.length && !loading ? (
          <p className="muted-text">
            {getLocalizedText(
              auth.language,
              "No plot data is available right now.",
              "இப்போது நிலத் தரவு இல்லை."
            )}
          </p>
        ) : null}
      </section>
    </div>
  );
}
