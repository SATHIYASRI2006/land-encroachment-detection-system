import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import Badge from "../components/Badge";
import Card from "../components/Card";
import {
  extractRegistrationFromDeed,
  getOfficialParcelBySurvey,
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
  boundary_coordinates: "",
};

const importantFields = new Set([
  "seller_name",
  "buyer_name",
  "survey_number",
  "area",
  "boundary_coordinates",
]);

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
    const addCollection = (collection, style) => {
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
    };

    addCollection(mapLayers?.official_parcel, {
      color: "#164e63",
      weight: 3,
      fillOpacity: 0.08,
    });
    addCollection(mapLayers?.claimed_boundary, {
      color: "#ca8a04",
      weight: 3,
      fillOpacity: 0.08,
    });
    addCollection(mapLayers?.government_land, {
      color: "#b91c1c",
      weight: 2,
      fillOpacity: 0.06,
      dashArray: "6 6",
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
      padding: [24, 24],
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

  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) {
      throw new Error("Boundary coordinates must be a JSON array or plain coordinate text.");
    }
    const normalized = parsed.map((pair) => [Number(pair[0]), Number(pair[1])]);
    if (normalized.length < 3 || normalized.some((pair) => Number.isNaN(pair[0]) || Number.isNaN(pair[1]))) {
      throw new Error("Enter at least three valid boundary points.");
    }
    return normalized;
  } catch (jsonError) {
    const coordinatePairs = [];
    const pairRegex = /(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)/g;
    let match;
    while ((match = pairRegex.exec(value)) !== null) {
      coordinatePairs.push([Number(match[1]), Number(match[2])]);
    }
    if (
      coordinatePairs.length < 3 ||
      coordinatePairs.some((pair) => Number.isNaN(pair[0]) || Number.isNaN(pair[1]))
    ) {
      throw new Error("Enter at least three boundary points.");
    }
    return coordinatePairs;
  }
}

function formatBoundaryCoordinates(points) {
  return (points || []).map((pair) => `${pair[0]}, ${pair[1]}`).join("\n");
}

function buildFeatureCollection(geometry, properties = {}) {
  if (!geometry) {
    return { type: "FeatureCollection", features: [] };
  }
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties,
        geometry,
      },
    ],
  };
}

function toPolygonGeometry(points) {
  if (!Array.isArray(points) || points.length < 3) {
    return null;
  }

  const ring = points.map((pair) => [Number(pair[1]), Number(pair[0])]);
  const first = ring[0];
  const last = ring[ring.length - 1];
  const closedRing =
    first && last && (first[0] !== last[0] || first[1] !== last[1]) ? [...ring, first] : ring;

  return {
    type: "Polygon",
    coordinates: [closedRing],
  };
}

function SummaryMetric({ label, value, tone = "" }) {
  return (
    <div className={`registration-metric ${tone}`.trim()}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function RegistrationVerificationPage() {
  const [form, setForm] = useState(initialForm);
  const [deedFile, setDeedFile] = useState(null);
  const [extraction, setExtraction] = useState(null);
  const [fieldStatus, setFieldStatus] = useState({});
  const [officialParcelInfo, setOfficialParcelInfo] = useState(null);
  const [officialBoundaryText, setOfficialBoundaryText] = useState("");
  const [result, setResult] = useState(null);
  const [records, setRecords] = useState([]);
  const [loadingRecords, setLoadingRecords] = useState(true);
  const [status, setStatus] = useState({ type: "", message: "" });
  const [loadingExtract, setLoadingExtract] = useState(false);
  const [loadingParcel, setLoadingParcel] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const resultSectionRef = useRef(null);

  const reviewReasons = result?.validation?.review_reasons || [];
  const currentPdfUrl = result?.generated_pdf?.download_url
    ? getReportDownloadUrl(result.generated_pdf.download_url)
    : "";
  const previewMapLayers = useMemo(() => {
    if (result?.map_layers) {
      return result.map_layers;
    }

    let claimedBoundaryGeometry = null;
    try {
      claimedBoundaryGeometry = toPolygonGeometry(parseBoundaryCoordinates(form.boundary_coordinates));
    } catch (error) {
      claimedBoundaryGeometry = null;
    }

    return {
      official_parcel: buildFeatureCollection(officialParcelInfo?.geometry_geojson, {
        layer: "official_parcel",
        survey_number: officialParcelInfo?.survey_number,
      }),
      claimed_boundary: buildFeatureCollection(claimedBoundaryGeometry, {
        layer: "claimed_boundary",
        survey_number: form.survey_number,
      }),
      government_land: buildFeatureCollection(null),
      overlap_highlight: buildFeatureCollection(null),
    };
  }, [form.boundary_coordinates, form.survey_number, officialParcelInfo, result]);

  useEffect(() => {
    let active = true;

    async function loadHistory() {
      setLoadingRecords(true);
      try {
        const response = await getRegistrationRecords();
        if (!active) {
          return;
        }
        setRecords(response?.data || []);
      } catch (error) {
        if (active) {
          setRecords([]);
        }
      } finally {
        if (active) {
          setLoadingRecords(false);
        }
      }
    }

    loadHistory();
    return () => {
      active = false;
    };
  }, []);

  function resetReference() {
    setOfficialParcelInfo(null);
    setOfficialBoundaryText("");
  }

  function resetWorkflowForNewDeed(nextFile) {
    setDeedFile(nextFile);
    setExtraction(null);
    setResult(null);
    setFieldStatus({});
    setStatus({ type: "", message: "" });
    resetReference();
    setForm((current) => ({
      ...initialForm,
      officer_notes: current.officer_notes,
    }));
  }

  function handleFieldChange(event) {
    const { name, value } = event.target;
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
    setFieldStatus((current) => ({
      ...current,
      [name]: value ? "confirmed" : current[name] || "missing",
    }));
    if (name === "survey_number") {
      resetReference();
    }
  }

  async function loadOfficialParcel(nextSurvey) {
    const surveyNumber = (nextSurvey || form.survey_number || "").trim();
    if (!surveyNumber) {
      setStatus({ type: "error", message: "Survey number is required to load the official parcel." });
      return;
    }

    setLoadingParcel(true);
    try {
      const response = await getOfficialParcelBySurvey(surveyNumber);
      const parcel = response?.data || null;
      setOfficialParcelInfo(parcel);
      setOfficialBoundaryText(formatBoundaryCoordinates(parcel?.boundary_coordinates || []));
    } catch (error) {
      resetReference();
      setStatus({
        type: "error",
        message: error.response?.data?.error?.message || "Could not load the official parcel reference.",
      });
    } finally {
      setLoadingParcel(false);
    }
  }

  async function handleExtract() {
    if (!deedFile) {
      setStatus({ type: "error", message: "Choose a deed file first." });
      return;
    }

    setLoadingExtract(true);
    setStatus({ type: "", message: "" });
    try {
      const response = await extractRegistrationFromDeed(deedFile);
      const preview = response?.data || {};
      const fields = preview.extracted_fields || {};
      setExtraction(preview);
      setFieldStatus(preview.field_confidence || {});
      setForm((current) => ({
        ...current,
        seller_name: fields.seller_name || current.seller_name,
        buyer_name: fields.buyer_name || current.buyer_name,
        survey_number: fields.survey_number || current.survey_number,
        area: fields.area ?? current.area,
        village: fields.village || current.village,
        district: fields.district || current.district,
        boundary_coordinates: fields.boundary_coordinates?.length
          ? formatBoundaryCoordinates(fields.boundary_coordinates)
          : current.boundary_coordinates,
      }));
      if (fields.survey_number) {
        await loadOfficialParcel(fields.survey_number);
      } else {
        resetReference();
      }
      setStatus({
        type: "success",
        message: "Deed extracted. Review the highlighted fields before verifying.",
      });
    } catch (error) {
      setExtraction(null);
      setStatus({
        type: "error",
        message: error.response?.data?.error?.message || "Could not extract deed details.",
      });
    } finally {
      setLoadingExtract(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setStatus({ type: "", message: "" });

    try {
      if (!officialParcelInfo) {
        throw new Error("Load the official parcel reference before verifying.");
      }

      const boundaryCoordinates = parseBoundaryCoordinates(form.boundary_coordinates);
      const response = await verifyRegistration({
        ...form,
        boundary_coordinates: boundaryCoordinates,
        uploaded_sale_deed: deedFile,
      });
      setResult(response?.data || null);
      setRecords((current) => {
        const nextRecord = response?.data?.registration_request;
        if (!nextRecord) {
          return current;
        }
        const filtered = current.filter((item) => item.id !== nextRecord.id);
        return [nextRecord, ...filtered];
      });
      setStatus({
        type: "success",
        message: "Verification complete. Review the decision and flagged reasons below.",
      });
      resultSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      setResult(null);
      setStatus({
        type: "error",
        message:
          error.response?.data?.error?.message ||
          error.message ||
          "Verification failed.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  const metrics = useMemo(() => {
    if (!result) {
      return {
        risk: "--",
        status: "--",
        similarity: "--",
      };
    }
    return {
      risk: result.result?.risk_level || "--",
      status: result.result?.verification_status || "--",
      similarity: Number(result.validation?.geometry_similarity_ratio || 0).toFixed(2),
    };
  }, [result]);

  function fieldClass(name) {
    const needsAttention = importantFields.has(name) && fieldStatus[name] !== "confirmed";
    return `form-field review-field${needsAttention ? " review-field-attention" : ""}`;
  }

  return (
    <div className="registration-page">
      <section className="registration-hero">
        <div>
          <p className="registration-kicker">Registration Check</p>
          <h1>Deed Review Workspace</h1>
        </div>
        <div className="registration-metrics">
          <SummaryMetric label="Risk" value={metrics.risk} />
          <SummaryMetric label="Decision" value={metrics.status} />
          <SummaryMetric label="Shape Match" value={metrics.similarity} />
        </div>
      </section>

      <section className="registration-shell">
        <Card className="registration-card registration-card-primary" eyebrow="Step 1" title="Upload and extract">
          <div className="form-stack">
            <label className="form-field">
              <span>Deed file</span>
              <input
                accept=".pdf,.txt,.md,.png,.jpg,.jpeg"
                onChange={(event) => resetWorkflowForNewDeed(event.target.files?.[0] || null)}
                type="file"
              />
            </label>
            <div className="inline-actions">
              <button disabled={!deedFile || loadingExtract} onClick={handleExtract} type="button">
                {loadingExtract ? "Extracting..." : "Extract details"}
              </button>
              {deedFile ? <span className="muted-text">{deedFile.name}</span> : null}
            </div>
            <div className="upload-stage-panel">
              <div className="upload-stage-hero">
                <div>
                  <p className="upload-stage-kicker">Upload Status</p>
                  <h3>{deedFile ? "Document ready for extraction" : "Waiting for a deed file"}</h3>
                </div>
                <div className="upload-stage-badge">
                  {deedFile ? (deedFile.name.split(".").pop() || "FILE").toUpperCase() : "NO FILE"}
                </div>
              </div>

              <div className="upload-stage-grid">
                <div className="upload-stage-tile">
                  <span>Selected file</span>
                  <strong>{deedFile ? deedFile.name : "No file selected yet"}</strong>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card className="registration-card" eyebrow="Step 2" title="Review highlighted fields">
          <form className="form-stack" onSubmit={handleSubmit}>
            <div className="detail-grid">
              <label className={fieldClass("seller_name")}>
                <span>Seller name</span>
                <input name="seller_name" onChange={handleFieldChange} required value={form.seller_name} />
              </label>
              <label className={fieldClass("buyer_name")}>
                <span>Buyer name</span>
                <input name="buyer_name" onChange={handleFieldChange} required value={form.buyer_name} />
              </label>
            </div>

            <div className="detail-grid">
              <label className={fieldClass("survey_number")}>
                <span>Survey number</span>
                <input name="survey_number" onChange={handleFieldChange} required value={form.survey_number} />
              </label>
              <label className={fieldClass("area")}>
                <span>Area</span>
                <input name="area" onChange={handleFieldChange} type="number" value={form.area} />
              </label>
            </div>

            <div className="detail-grid">
              <label className="form-field review-field">
                <span>Village</span>
                <input name="village" onChange={handleFieldChange} value={form.village} />
              </label>
              <label className="form-field review-field">
                <span>District</span>
                <input name="district" onChange={handleFieldChange} value={form.district} />
              </label>
            </div>

            <label className={fieldClass("boundary_coordinates")}>
              <span>Claimed boundary coordinates</span>
              <textarea
                name="boundary_coordinates"
                onChange={handleFieldChange}
                required
                rows="6"
                placeholder={"13.0812, 80.2620\n13.0812, 80.2652\n13.0838, 80.2652"}
                value={form.boundary_coordinates}
              />
            </label>

            <label className="form-field">
              <span>Officer notes</span>
              <textarea
                name="officer_notes"
                onChange={handleFieldChange}
                rows="3"
                value={form.officer_notes}
              />
            </label>

            {extraction?.missing_fields?.length ? (
              <div className="status-warning">
                Missing from extraction: {extraction.missing_fields.join(", ")}
              </div>
            ) : null}

            {status.message ? (
              <div className={status.type === "error" ? "status-error" : "status-success"}>
                {status.message}
              </div>
            ) : null}

            <div className="inline-actions">
              <button disabled={loadingParcel} onClick={() => loadOfficialParcel()} type="button">
                {loadingParcel ? "Loading official parcel..." : "Load official reference"}
              </button>
              <button disabled={submitting} type="submit">
                {submitting ? "Verifying..." : "Verify registration"}
              </button>
            </div>
          </form>
        </Card>
      </section>

      <section className="registration-shell registration-shell-secondary">
        <Card className="registration-card" eyebrow="Step 3" title="Official parcel reference">
          {officialParcelInfo ? (
            <div className="summary-list">
              <div className="summary-row">
                <span>Parcel</span>
                <strong>{officialParcelInfo.parcel_id}</strong>
              </div>
              <div className="summary-row">
                <span>Survey</span>
                <strong>{officialParcelInfo.survey_number}</strong>
              </div>
              <div className="summary-row">
                <span>Owner</span>
                <strong>{officialParcelInfo.owner_name}</strong>
              </div>
              <label className="form-field">
                <span>Official boundary</span>
                <textarea readOnly rows="6" value={officialBoundaryText} />
              </label>
            </div>
          ) : null}
        </Card>

        <Card className="registration-card" eyebrow="Extraction" title="What the system found">
          {extraction ? (
            <div className="summary-list">
              <div className="summary-row">
                <span>Seller</span>
                <strong>{extraction.extracted_fields?.seller_name || "--"}</strong>
              </div>
              <div className="summary-row">
                <span>Buyer</span>
                <strong>{extraction.extracted_fields?.buyer_name || "--"}</strong>
              </div>
              <div className="summary-row">
                <span>Survey</span>
                <strong>{extraction.extracted_fields?.survey_number || "--"}</strong>
              </div>
              <div className="summary-row">
                <span>Coordinate pairs</span>
                <strong>{extraction.extracted_fields?.boundary_coordinates?.length || 0}</strong>
              </div>
            </div>
          ) : null}
        </Card>
      </section>

      <section className="registration-results" ref={resultSectionRef}>
        <Card className="registration-card registration-card-primary" eyebrow="Result" title="Verification outcome">
          {result ? (
            <div className="form-stack">
              <div className="registration-result-head">
                <Badge tone={(result.result?.risk_level || "low").toLowerCase()}>
                  {result.result?.risk_level}
                </Badge>
                <strong>{result.result?.verification_status}</strong>
              </div>
              <div className="summary-list">
                <div className="summary-row">
                  <span>Risk score</span>
                  <strong>{result.result?.risk_score}</strong>
                </div>
                <div className="summary-row">
                  <span>Geometry similarity</span>
                  <strong>{Number(result.validation?.geometry_similarity_ratio || 0).toFixed(2)}</strong>
                </div>
                <div className="summary-row">
                  <span>Official coverage</span>
                  <strong>{Number(result.validation?.official_coverage_ratio || 0).toFixed(2)}</strong>
                </div>
                <div className="summary-row">
                  <span>PDF report</span>
                  <strong>
                    {currentPdfUrl ? (
                      <a href={currentPdfUrl} rel="noreferrer" target="_blank">
                        Open report
                      </a>
                    ) : (
                      "--"
                    )}
                  </strong>
                </div>
              </div>
              {reviewReasons.length ? (
                <div className="review-reasons">
                  {reviewReasons.map((reason) => (
                    <div className="review-reason" key={reason}>
                      {reason}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </Card>

        <Card className="registration-card" eyebrow="Map" title="Official parcel vs claimed deed boundary">
          <RegistrationMap mapLayers={previewMapLayers} />
        </Card>
      </section>

      <section>
        <Card className="registration-card" eyebrow="History" title="Recent verification history">
          {loadingRecords ? (
            <p className="muted-text">Loading saved verification results...</p>
          ) : records.length ? (
            <div className="registration-history-list">
              {records.map((record) => {
                const reportUrl = record.generated_deed_pdf
                  ? getReportDownloadUrl(`/reports/${record.generated_deed_pdf}`)
                  : "";
                return (
                  <div className="registration-history-item" key={record.id}>
                    <div className="registration-history-head">
                      <div>
                        <strong>
                          {record.extracted_survey_number || "Survey pending"} · {record.buyer_name}
                        </strong>
                        <p className="muted-text">
                          {record.uploaded_sale_deed || "Structured entry"} · {record.created_at || "--"}
                        </p>
                      </div>
                      <Badge tone={(record.risk_level || "low").toLowerCase()}>
                        {record.risk_level || "LOW"}
                      </Badge>
                    </div>
                    <div className="registration-history-grid">
                      <div>
                        <span>Status</span>
                        <strong>{record.verification_status || "--"}</strong>
                      </div>
                      <div>
                        <span>Risk score</span>
                        <strong>{record.risk_score ?? "--"}</strong>
                      </div>
                      <div>
                        <span>Overlap</span>
                        <strong>{record.government_land_overlap ? "Yes" : "No"}</strong>
                      </div>
                      <div>
                        <span>Report</span>
                        <strong>
                          {reportUrl ? (
                            <a href={reportUrl} rel="noreferrer" target="_blank">
                              Open report
                            </a>
                          ) : (
                            "--"
                          )}
                        </strong>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="muted-text">No saved verification history yet. Verified deeds will appear here.</p>
          )}
        </Card>
      </section>
    </div>
  );
}
