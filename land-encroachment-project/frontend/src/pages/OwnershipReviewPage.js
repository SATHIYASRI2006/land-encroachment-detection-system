import { useEffect, useMemo, useState } from "react";

import Badge from "../components/Badge";
import Card from "../components/Card";
import { getLocalizedText } from "../config/appContent";
import { createClaim, getClaims, updateClaim } from "../services/api";

function buildRectangleBoundary(lat, lng, span = 0.0012) {
  const latitude = Number(lat);
  const longitude = Number(lng);
  return {
    type: "Polygon",
    coordinates: [[
      [longitude - span, latitude - span],
      [longitude + span, latitude - span],
      [longitude + span, latitude + span],
      [longitude - span, latitude + span],
      [longitude - span, latitude - span],
    ]],
  };
}

function scaleBoundary(boundaryGeojson, factor = 1) {
  const ring = boundaryGeojson?.coordinates?.[0];
  if (!Array.isArray(ring) || ring.length < 4) {
    return boundaryGeojson;
  }

  const points = ring.slice(0, -1);
  const centroid = points.reduce(
    (acc, [lng, lat]) => ({
      lng: acc.lng + lng / points.length,
      lat: acc.lat + lat / points.length,
    }),
    { lng: 0, lat: 0 }
  );

  const scaled = points.map(([lng, lat]) => [
    centroid.lng + (lng - centroid.lng) * factor,
    centroid.lat + (lat - centroid.lat) * factor,
  ]);

  return {
    type: "Polygon",
    coordinates: [[...scaled, scaled[0]]],
  };
}

const initialForm = {
  claimant_name: "",
  claimed_plot_label: "",
  claimed_owner_name: "",
  claim_reference: "",
  survey_no: "",
  adjacent_plot_id: "",
  lat: "",
  lng: "",
  geometry_mode: "reference",
  expansion_factor: "1.08",
  boundary_geojson_text: "",
  notes: "",
};

export default function OwnershipReviewPage({ auth, plots }) {
  const [claims, setClaims] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [updatingId, setUpdatingId] = useState(null);

  async function loadClaims() {
    try {
      const response = await getClaims();
      setClaims(response?.data || []);
    } catch (error) {
      setClaims([]);
    }
  }

  useEffect(() => {
    loadClaims();
  }, []);

  const selectedReferencePlot = useMemo(
    () => plots.find((plot) => plot.id === form.adjacent_plot_id) || null,
    [plots, form.adjacent_plot_id]
  );

  const claimSummary = useMemo(() => {
    return {
      high: claims.filter((item) => item.risk_flag === "High").length,
      medium: claims.filter((item) => item.risk_flag === "Medium").length,
      open: claims.filter((item) => item.status !== "Resolved").length,
    };
  }, [claims]);

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function buildClaimGeometry() {
    if (form.geometry_mode === "geojson" && form.boundary_geojson_text.trim()) {
      return JSON.parse(form.boundary_geojson_text);
    }

    if (form.geometry_mode === "reference" && selectedReferencePlot?.boundary_geojson) {
      return scaleBoundary(
        selectedReferencePlot.boundary_geojson,
        Number(form.expansion_factor || 1.08)
      );
    }

    return buildRectangleBoundary(form.lat, form.lng);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");

    try {
      const payload = {
        claimant_name: form.claimant_name,
        claimed_plot_label: form.claimed_plot_label,
        claimed_owner_name: form.claimed_owner_name,
        claim_reference: form.claim_reference,
        survey_no: form.survey_no,
        adjacent_plot_id: form.adjacent_plot_id,
        notes: form.notes,
        claim_boundary_geojson: buildClaimGeometry(),
      };

      await createClaim(payload);
      setForm(initialForm);
      setStatus(
        getLocalizedText(
          auth.language,
          "Ownership claim recorded and evaluated successfully.",
          "Ownership claim recorded and evaluated successfully."
        )
      );
      await loadClaims();
    } catch (error) {
      setStatus(
        error.response?.data?.error?.message ||
          getLocalizedText(
            auth.language,
            "Failed to record ownership claim.",
            "Failed to record ownership claim."
          )
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function setClaimStatus(claimId, nextStatus) {
    try {
      setUpdatingId(claimId);
      await updateClaim(claimId, { status: nextStatus });
      await loadClaims();
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div>
          <p className="section-eyebrow">
            {getLocalizedText(auth.language, "Ownership Review", "Ownership Review")}
          </p>
          <h1 className="page-title">Boundary and title conflict review</h1>
        </div>
      </section>

      <section className="kpi-grid kpi-grid-compact">
        <Card className="kpi-card">
          <p className="kpi-label">Open Claims</p>
          <strong className="kpi-value">{claimSummary.open}</strong>
        </Card>
        <Card className="kpi-card">
          <p className="kpi-label">High Conflict</p>
          <strong className="kpi-value">{claimSummary.high}</strong>
        </Card>
        <Card className="kpi-card">
          <p className="kpi-label">Medium Conflict</p>
          <strong className="kpi-value">{claimSummary.medium}</strong>
        </Card>
      </section>

      <section className="overview-grid admin-grid">
        <Card eyebrow="Claim Intake" title="Submit ownership claim for evaluation">
          <form className="form-stack" onSubmit={handleSubmit}>
            <div className="detail-grid">
              <label className="form-field">
                <span>Claimant name</span>
                <input name="claimant_name" value={form.claimant_name} onChange={handleChange} required />
              </label>
              <label className="form-field">
                <span>Claim label</span>
                <input name="claimed_plot_label" value={form.claimed_plot_label} onChange={handleChange} required />
              </label>
            </div>

            <div className="detail-grid">
              <label className="form-field">
                <span>Claimed owner</span>
                <input name="claimed_owner_name" value={form.claimed_owner_name} onChange={handleChange} />
              </label>
              <label className="form-field">
                <span>Reference / deed no</span>
                <input name="claim_reference" value={form.claim_reference} onChange={handleChange} />
              </label>
            </div>

            <div className="detail-grid">
              <label className="form-field">
                <span>Survey no</span>
                <input name="survey_no" value={form.survey_no} onChange={handleChange} />
              </label>
              <label className="form-field">
                <span>Nearby monitored plot</span>
                <select name="adjacent_plot_id" value={form.adjacent_plot_id} onChange={handleChange}>
                  <option value="">Select plot</option>
                  {plots.map((plot) => (
                    <option key={plot.id} value={plot.id}>
                      {plot.plotName}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="detail-grid">
              <label className="form-field">
                <span>Geometry source</span>
                <select name="geometry_mode" value={form.geometry_mode} onChange={handleChange}>
                  <option value="reference">Use selected plot boundary</option>
                  <option value="coordinates">Use approximate lat / lng box</option>
                  <option value="geojson">Paste exact boundary GeoJSON</option>
                </select>
              </label>

              {form.geometry_mode === "reference" ? (
                <label className="form-field">
                  <span>Boundary expansion factor</span>
                  <select name="expansion_factor" value={form.expansion_factor} onChange={handleChange}>
                    <option value="1.00">Exact parcel edge</option>
                    <option value="1.08">8% expansion</option>
                    <option value="1.15">15% expansion</option>
                    <option value="1.25">25% expansion</option>
                  </select>
                </label>
              ) : null}
            </div>

            {form.geometry_mode === "coordinates" ? (
              <div className="detail-grid">
                <label className="form-field">
                  <span>Approx latitude</span>
                  <input name="lat" type="number" value={form.lat} onChange={handleChange} required />
                </label>
                <label className="form-field">
                  <span>Approx longitude</span>
                  <input name="lng" type="number" value={form.lng} onChange={handleChange} required />
                </label>
              </div>
            ) : null}

            {form.geometry_mode === "geojson" ? (
              <label className="form-field">
                <span>Boundary GeoJSON</span>
                <textarea
                  name="boundary_geojson_text"
                  rows="6"
                  value={form.boundary_geojson_text}
                  onChange={handleChange}
                  placeholder='{"type":"Polygon","coordinates":[[[80.26,13.08],[80.27,13.08],[80.27,13.09],[80.26,13.09],[80.26,13.08]]]}'
                  required
                />
              </label>
            ) : null}

            <label className="form-field">
              <span>Notes</span>
              <textarea name="notes" rows="4" value={form.notes} onChange={handleChange} />
            </label>

            {status ? (
              <div className={status.toLowerCase().includes("failed") ? "status-error" : "status-success"}>
                {status}
              </div>
            ) : null}

            <button disabled={submitting} type="submit">
              {submitting ? "Evaluating claim..." : "Evaluate ownership claim"}
            </button>
          </form>
        </Card>

        <Card eyebrow="Evaluation Rules" title="Signals used by the conflict engine">
          <div className="summary-list">
            <div className="summary-row">
              <span>Protected government layer overlap</span>
              <strong>Priority weighted</strong>
            </div>
            <div className="summary-row">
              <span>Official parcel boundary intersection</span>
              <strong>Checked</strong>
            </div>
            <div className="summary-row">
              <span>Survey / owner mismatch against closest record</span>
              <strong>Scored</strong>
            </div>
            <div className="summary-row">
              <span>Multiple parcel intersections</span>
              <strong>Escalated</strong>
            </div>
          </div>
        </Card>
      </section>

      <section className="ui-card">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Claimant</th>
                <th>Claim Label</th>
                <th>Survey</th>
                <th>Risk</th>
                <th>Score</th>
                <th>Overlap</th>
                <th>Status</th>
                <th>Matched Record</th>
                <th>Conflict Reason</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((claim) => (
                <tr key={claim.id}>
                  <td>{claim.claimant_name}</td>
                  <td>{claim.claimed_plot_label}</td>
                  <td>{claim.survey_no || "--"}</td>
                  <td>
                    <Badge tone={claim.risk_flag.toLowerCase()}>{claim.risk_flag}</Badge>
                  </td>
                  <td>{claim.risk_score ?? "--"}</td>
                  <td>{Number(claim.overlap_percent || 0).toFixed(2)}%</td>
                  <td>{claim.status}</td>
                  <td>{claim.matched_plot_name || claim.matched_plot_id || "--"}</td>
                  <td>{claim.conflict_reason}</td>
                  <td>
                    <div className="inline-actions">
                      <button
                        disabled={updatingId === claim.id}
                        onClick={() => setClaimStatus(claim.id, "Investigating")}
                        type="button"
                      >
                        Review
                      </button>
                      <button
                        className="ghost-button"
                        disabled={updatingId === claim.id}
                        onClick={() => setClaimStatus(claim.id, "Resolved")}
                        type="button"
                      >
                        Resolve
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
