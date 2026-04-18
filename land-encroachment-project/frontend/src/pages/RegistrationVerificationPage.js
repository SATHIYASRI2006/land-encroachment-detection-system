import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import Badge from "../components/Badge";
import Card from "../components/Card";
import { getLocalizedText } from "../config/appContent";
import {
  getRegistrationRecords,
  getReportDownloadUrl,
  verifyRegistration,
} from "../services/api";

const initialForm = {
  seller_name: "",
  buyer_name: "",
  survey_number: "",
  area: "",
  village: "",
  district: "",
  officer_notes: "",
  boundary_coordinates: "[[13.0812, 80.2620], [13.0812, 80.2652], [13.0838, 80.2652], [13.0838, 80.2620]]",
};

function RegistrationMap({ mapLayers }) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const layerRef = useRef(null);

  useEffect(() => {
    if (mapInstance.current || !mapRef.current) {
      return undefined;
    }

    mapInstance.current = L.map(mapRef.current, {
      zoomControl: true,
      zoomAnimation: false,
      fadeAnimation: false,
      markerZoomAnimation: false,
    }).setView([13.0827, 80.2707], 12);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(mapInstance.current);

    layerRef.current = L.layerGroup().addTo(mapInstance.current);

    return () => {
      if (mapInstance.current) {
        mapInstance.current.off();
        mapInstance.current.remove();
        mapInstance.current = null;
      }
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapInstance.current;
    const layerGroup = layerRef.current;
    if (!map || !layerGroup) {
      return undefined;
    }

    layerGroup.clearLayers();
    const bounds = [];

    function addCollection(collection, style) {
      if (!collection?.features?.length) {
        return;
      }
      const layer = L.geoJSON(collection, {
        style: typeof style === "function" ? style : () => style,
      });
      layer.eachLayer((item) => {
        if (item.getBounds) {
          bounds.push(item.getBounds());
        }
      });
      layerGroup.addLayer(layer);
    }

    addCollection(mapLayers?.government_land, {
      color: "#b91c1c",
      weight: 2,
      fillOpacity: 0.06,
      dashArray: "6 6",
    });
    addCollection(mapLayers?.official_parcel, {
      color: "#2563eb",
      weight: 3,
      fillOpacity: 0.08,
    });
    addCollection(mapLayers?.claimed_boundary, {
      color: "#d97706",
      weight: 3,
      fillOpacity: 0.08,
    });
    addCollection(mapLayers?.overlap_highlight, {
      color: "#dc2626",
      weight: 3,
      fillColor: "#ef4444",
      fillOpacity: 0.35,
    });

    map.invalidateSize({ animate: false, pan: false });
    if (!bounds.length) {
      return undefined;
    }

    const mergedBounds = bounds.reduce((acc, item) => acc.extend(item), bounds[0]);
    map.fitBounds(mergedBounds, {
      padding: [26, 26],
      maxZoom: 16,
      animate: false,
    });

    return undefined;
  }, [mapLayers]);

  return <div ref={mapRef} className="registration-map-canvas" />;
}

function parseBoundaryCoordinates(value) {
  if (!value.trim()) {
    return [];
  }
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed)) {
    throw new Error("Boundary coordinates must be a JSON array of [lat, lng] points.");
  }
  return parsed;
}

export default function RegistrationVerificationPage({ auth }) {
  const [form, setForm] = useState(initialForm);
  const [records, setRecords] = useState([]);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState({ type: "", message: "" });
  const resultSectionRef = useRef(null);

  const latestRecord = records[0] || null;
  const currentPdfUrl = result?.generated_pdf?.download_url
    ? getReportDownloadUrl(result.generated_pdf.download_url)
    : latestRecord?.generated_deed_pdf
      ? getReportDownloadUrl(`/reports/${latestRecord.generated_deed_pdf}`)
      : "";

  useEffect(() => {
    let active = true;

    async function loadRecords() {
      try {
        const response = await getRegistrationRecords();
        if (active) {
          setRecords(response?.data || []);
        }
      } catch (error) {
        if (active) {
          setRecords([]);
        }
      }
    }

    loadRecords();
    return () => {
      active = false;
    };
  }, []);

  const summary = useMemo(() => {
    if (!result) {
      return {
        risk: "--",
        status: "--",
        overlap: "0",
      };
    }
    return {
      risk: result.result?.risk_level || "--",
      status: result.result?.verification_status || "--",
      overlap: Number(result.result?.encroachment_area || 0).toFixed(6),
    };
  }, [result]);

  function handleFieldChange(event) {
    const { name, value } = event.target;
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setStatus({ type: "", message: "" });

    try {
      let boundaryCoordinates;
      try {
        boundaryCoordinates = parseBoundaryCoordinates(form.boundary_coordinates);
      } catch (parseError) {
        setStatus({
          type: "error",
          message:
            parseError.message ||
            "Boundary coordinates must be valid JSON like [[13.0812, 80.2620], [13.0812, 80.2652], [13.0838, 80.2652], [13.0838, 80.2620]].",
        });
        setSubmitting(false);
        return;
      }

      const response = await verifyRegistration({
        seller_name: form.seller_name,
        buyer_name: form.buyer_name,
        survey_number: form.survey_number,
        area: form.area,
        village: form.village,
        district: form.district,
        officer_notes: form.officer_notes,
        boundary_coordinates: boundaryCoordinates,
      });
      setResult(response?.data || null);
      setStatus({
        type: "success",
        message: getLocalizedText(
          auth.language,
          "Registration record generated and verified successfully.",
          "Registration record generated and verified successfully."
        ),
      });

      const generatedPdfUrl = response?.data?.generated_pdf?.download_url
        ? getReportDownloadUrl(response.data.generated_pdf.download_url)
        : "";
      if (generatedPdfUrl) {
        window.open(generatedPdfUrl, "_blank", "noopener,noreferrer");
      }
      resultSectionRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      try {
        const recordResponse = await getRegistrationRecords();
        setRecords(recordResponse?.data || []);
      } catch (refreshError) {
        // Keep the successful verification result visible even if record refresh fails.
      }
    } catch (error) {
      setStatus({
        type: "error",
        message:
          error.response?.data?.error?.message ||
          error.message ||
          getLocalizedText(
            auth.language,
            "Failed to verify registration request.",
            "Failed to verify registration request."
          ),
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="kpi-grid kpi-grid-compact">
        <Card className="kpi-card">
          <p className="kpi-label">Risk Level</p>
          <strong className="kpi-value">{summary.risk}</strong>
        </Card>
        <Card className="kpi-card">
          <p className="kpi-label">Verification</p>
          <strong className="kpi-value">{summary.status}</strong>
        </Card>
        <Card className="kpi-card">
          <p className="kpi-label">Encroachment Area</p>
          <strong className="kpi-value">{summary.overlap}</strong>
        </Card>
      </section>

      <section className="overview-grid registration-grid">
        <Card eyebrow="Input" title="Create registration record">
          <form className="form-stack" onSubmit={handleSubmit}>
            <div className="detail-grid">
              <label className="form-field">
                <span>Seller name</span>
                <input name="seller_name" onChange={handleFieldChange} required value={form.seller_name} />
              </label>
              <label className="form-field">
                <span>Buyer name</span>
                <input name="buyer_name" onChange={handleFieldChange} required value={form.buyer_name} />
              </label>
            </div>

            <div className="detail-grid">
              <label className="form-field">
                <span>Survey number</span>
                <input name="survey_number" onChange={handleFieldChange} required value={form.survey_number} />
              </label>
              <label className="form-field">
                <span>Area</span>
                <input name="area" onChange={handleFieldChange} type="number" value={form.area} />
              </label>
            </div>

            <div className="detail-grid">
              <label className="form-field">
                <span>Village</span>
                <input name="village" onChange={handleFieldChange} value={form.village} />
              </label>
              <label className="form-field">
                <span>District</span>
                <input name="district" onChange={handleFieldChange} value={form.district} />
              </label>
            </div>

            <label className="form-field">
              <span>Boundary coordinates JSON</span>
              <textarea
                name="boundary_coordinates"
                onChange={handleFieldChange}
                required
                rows="6"
                value={form.boundary_coordinates}
              />
            </label>

            <label className="form-field">
              <span>Officer notes</span>
              <textarea
                name="officer_notes"
                onChange={handleFieldChange}
                rows="4"
                value={form.officer_notes}
              />
            </label>

            <p className="muted-text">
              The system will generate a standard PDF file from this data and store it with the approval status for future records.
            </p>

            {status.message ? (
              <div className={status.type === "error" ? "status-error" : "status-success"}>
                {status.message}
              </div>
            ) : null}

            <button disabled={submitting} type="submit">
              {submitting ? "Generating record..." : "Generate and verify"}
            </button>
          </form>
        </Card>

        <Card eyebrow="Records" title="Recent stored registration records">
          {records.length ? (
            <div className="summary-list">
              {records.slice(0, 6).map((record) => (
                <div className="summary-row" key={record.id}>
                  <span>
                    {record.extracted_survey_number || "--"} / {record.buyer_name}
                  </span>
                  <span className="registration-record-actions">
                    <strong>{record.verification_status}</strong>
                    {record.generated_deed_pdf ? (
                      <a
                        href={getReportDownloadUrl(`/reports/${record.generated_deed_pdf}`)}
                        rel="noreferrer"
                        target="_blank"
                      >
                        Open PDF
                      </a>
                    ) : (
                      <span className="muted-text">No PDF</span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted-text">Stored registration records will appear here.</p>
          )}
        </Card>
      </section>

      <section className="overview-grid registration-results-grid" ref={resultSectionRef}>
        <Card eyebrow="Result" title="Verification outcome">
          {result ? (
            <div className="summary-list">
              <div className="summary-row">
                <span>Risk score</span>
                <strong>{result.result?.risk_score}</strong>
              </div>
              <div className="summary-row">
                <span>Risk level</span>
                <Badge tone={(result.result?.risk_level || "low").toLowerCase()}>
                  {result.result?.risk_level}
                </Badge>
              </div>
              <div className="summary-row">
                <span>Verification status</span>
                <strong>{result.result?.verification_status}</strong>
              </div>
              <div className="summary-row">
                <span>Generated PDF</span>
                <strong>
                  {currentPdfUrl ? (
                    <a href={currentPdfUrl} rel="noreferrer" target="_blank">
                      Open generated PDF
                    </a>
                  ) : (
                    "--"
                  )}
                </strong>
              </div>
            </div>
          ) : (
            <p className="muted-text">Run a verification to generate the record and see the decision.</p>
          )}
        </Card>

        <Card eyebrow="Checks" title="Spatial validation breakdown">
          {result ? (
            <div className="summary-list">
              <div className="summary-row">
                <span>Area mismatch</span>
                <strong>{result.validation?.area_mismatch ? "Yes" : "No"}</strong>
              </div>
              <div className="summary-row">
                <span>Boundary expansion</span>
                <strong>{result.validation?.boundary_expansion ? "Yes" : "No"}</strong>
              </div>
              <div className="summary-row">
                <span>Government overlap</span>
                <strong>{result.validation?.government_land_overlap ? "Yes" : "No"}</strong>
              </div>
              <div className="summary-row">
                <span>Official parcel intersection</span>
                <strong>
                  {Number(result.validation?.official_parcel_intersection_ratio || 0).toFixed(2)}
                </strong>
              </div>
            </div>
          ) : (
            <p className="muted-text">Validation results will appear here after verification.</p>
          )}
        </Card>
      </section>

      <Card eyebrow="GeoJSON Map" title="Official parcel vs claimed parcel">
        <RegistrationMap mapLayers={result?.map_layers} />
      </Card>

      <section className="overview-grid registration-results-grid">
        <Card eyebrow="Entered Data" title="Structured registration values">
          {result ? (
            <div className="summary-list">
              <div className="summary-row">
                <span>Survey number</span>
                <strong>{result.ocr_extraction?.survey_number || "--"}</strong>
              </div>
              <div className="summary-row">
                <span>Area</span>
                <strong>{result.ocr_extraction?.area ?? "--"}</strong>
              </div>
              <div className="summary-row">
                <span>Coordinate pairs</span>
                <strong>{result.ocr_extraction?.coordinates?.length || 0}</strong>
              </div>
            </div>
          ) : (
            <p className="muted-text">Structured registration details will appear here.</p>
          )}
        </Card>

        <Card eyebrow="Official Parcel" title="Matched parcel record">
          {result ? (
            <div className="summary-list">
              <div className="summary-row">
                <span>Parcel ID</span>
                <strong>{result.official_parcel?.parcel_id}</strong>
              </div>
              <div className="summary-row">
                <span>Survey number</span>
                <strong>{result.official_parcel?.survey_number}</strong>
              </div>
              <div className="summary-row">
                <span>Owner</span>
                <strong>{result.official_parcel?.owner_name}</strong>
              </div>
              <div className="summary-row">
                <span>Area</span>
                <strong>{result.official_parcel?.area}</strong>
              </div>
            </div>
          ) : (
            <p className="muted-text">The matching official parcel will be shown here.</p>
          )}
        </Card>
      </section>
    </div>
  );
}
