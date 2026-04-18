import { useMemo, useState } from "react";

import Card from "../components/Card";
import { getLocalizedText } from "../config/appContent";
import { uploadPlotBundle } from "../services/api";

const YEAR_FIELDS = [2021, 2022, 2023, 2024];

const initialFields = {
  plot_id: "",
  location_name: "",
  lat: "",
  lng: "",
  area: "",
  survey_no: "",
  owner_name: "",
  village: "",
  district: "",
  operator_note: "",
};

export default function AdminPage({ auth, plots, alerts, onUploadSuccess }) {
  const [fields, setFields] = useState(initialFields);
  const [images, setImages] = useState({
    2021: null,
    2022: null,
    2023: null,
    2024: null,
  });
  const [status, setStatus] = useState({
    type: "",
    message: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const recentUploads = useMemo(() => {
    return plots.slice(0, 5).map((plot) => ({
      id: plot.id,
      file: plot.image_years?.length
        ? `Years: ${plot.image_years.join(", ")}`
        : "No images",
      status: plot.risk,
    }));
  }, [plots]);

  function handleFieldChange(event) {
    const { name, value } = event.target;
    setFields((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function handleImageChange(year, file) {
    setImages((current) => ({
      ...current,
      [year]: file || null,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setStatus({ type: "", message: "" });

    try {
      const response = await uploadPlotBundle({
        fields,
        images,
      });

      setStatus({
        type: "success",
        message: `${response.message}. Uploaded years: ${response.uploaded_years.join(", ")}`,
      });
      setFields(initialFields);
      setImages({
        2021: null,
        2022: null,
        2023: null,
        2024: null,
      });
      await onUploadSuccess?.();
    } catch (error) {
      setStatus({
        type: "error",
        message:
          error.response?.data?.error || "Upload failed. Please check the form.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div>
          <p className="section-eyebrow">
            {getLocalizedText(auth.language, "Admin Panel", "Admin Panel")}
          </p>
          <h1 className="page-title">Governance and control room workspace</h1>
          <p className="body-copy">
            Upload parcel data, manage operational evidence, and maintain audit-ready monitoring records.
          </p>
        </div>
        <div className="hero-summary">
          <span>Compliance</span>
          <strong>Audit Ready</strong>
        </div>
      </section>

      <section className="overview-grid">
        <Card eyebrow="Operations" title="Platform health">
          <div className="summary-list">
            <div className="summary-row">
              <span>Tracked plots</span>
              <strong>{plots.length}</strong>
            </div>
            <div className="summary-row">
              <span>Open alerts</span>
              <strong>{alerts.length}</strong>
            </div>
            <div className="summary-row">
              <span>Evidence sync</span>
              <strong>Healthy</strong>
            </div>
          </div>
        </Card>

        <Card eyebrow="Industry Features" title="Admin priorities">
          <div className="insight-grid">
            <div className="insight-pill"><strong>Role-based access</strong><span>Separate admin workflow</span></div>
            <div className="insight-pill"><strong>Audit trail</strong><span>Upload-ready documentation</span></div>
            <div className="insight-pill"><strong>Case governance</strong><span>Escalation monitoring</span></div>
          </div>
        </Card>
      </section>

      <section className="overview-grid admin-grid">
        <Card eyebrow="Upload Center" title="Upload imagery and plot datasets">
          <form className="form-stack" onSubmit={handleSubmit}>
            <label className="form-field">
              <span>Plot ID</span>
              <input
                name="plot_id"
                onChange={handleFieldChange}
                placeholder="plot8"
                required
                value={fields.plot_id}
              />
            </label>
            <label className="form-field">
              <span>Location name</span>
              <input
                name="location_name"
                onChange={handleFieldChange}
                placeholder="Madhavaram Canal Edge"
                required
                value={fields.location_name}
              />
            </label>
            <div className="detail-grid">
              <label className="form-field">
                <span>Latitude</span>
                <input
                  name="lat"
                  onChange={handleFieldChange}
                  placeholder="13.0827"
                  required
                  type="number"
                  value={fields.lat}
                />
              </label>
              <label className="form-field">
                <span>Longitude</span>
                <input
                  name="lng"
                  onChange={handleFieldChange}
                  placeholder="80.2707"
                  required
                  type="number"
                  value={fields.lng}
                />
              </label>
            </div>
            <div className="detail-grid">
              <label className="form-field">
                <span>Area</span>
                <input
                  name="area"
                  onChange={handleFieldChange}
                  placeholder="Pallikaranai"
                  value={fields.area}
                />
              </label>
              <label className="form-field">
                <span>Survey number</span>
                <input
                  name="survey_no"
                  onChange={handleFieldChange}
                  placeholder="S.No 14/2B"
                  value={fields.survey_no}
                />
              </label>
            </div>
            <div className="detail-grid">
              <label className="form-field">
                <span>Owner name</span>
                <input
                  name="owner_name"
                  onChange={handleFieldChange}
                  placeholder="Revenue Department"
                  value={fields.owner_name}
                />
              </label>
              <label className="form-field">
                <span>Village</span>
                <input
                  name="village"
                  onChange={handleFieldChange}
                  placeholder="Perungudi"
                  value={fields.village}
                />
              </label>
            </div>
            <label className="form-field">
              <span>District</span>
              <input
                name="district"
                onChange={handleFieldChange}
                placeholder="Chennai"
                value={fields.district}
              />
            </label>
            {YEAR_FIELDS.map((year) => (
              <label className="form-field" key={year}>
                <span>{`Plot image for ${year}`}</span>
                <input
                  accept=".png,.jpg,.jpeg"
                  onChange={(event) =>
                    handleImageChange(year, event.target.files?.[0])
                  }
                  type="file"
                />
              </label>
            ))}
            <label className="form-field">
              <span>Operator note</span>
              <textarea
                name="operator_note"
                onChange={handleFieldChange}
                rows="4"
                placeholder="Add enforcement or field remarks for this upload batch..."
                value={fields.operator_note}
              />
            </label>
            {status.message ? (
              <div className={status.type === "error" ? "status-error" : "status-success"}>
                {status.message}
              </div>
            ) : null}
            <button disabled={submitting} type="submit">
              {submitting ? "Uploading plot bundle..." : "Upload plot to database"}
            </button>
          </form>
        </Card>

        <Card eyebrow="Queue" title="Recent upload and compliance queue">
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>File</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {recentUploads.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.file}</td>
                    <td>{item.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>
    </div>
  );
}
