import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import Badge from "../components/Badge";
import Card from "../components/Card";
import Dashboard from "../components/Dashboard";
import ImagePanel from "../components/ImagePanel";
import MapView from "../components/MapView";
import { getLocalizedText } from "../config/appContent";

export default function MapPage({
  auth,
  enrichPlot,
  loadError,
  plots,
  selectedPlot,
  setSelectedPlotId,
  loading,
}) {
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const plotId = searchParams.get("plot");
    if (plotId) {
      setSelectedPlotId(plotId);
      enrichPlot?.(plotId);
    }
  }, [enrichPlot, searchParams, setSelectedPlotId]);

  return (
    <div className="page-stack">
      <section className="page-intro page-intro-split">
        <div>
          <p className="section-eyebrow">
            {getLocalizedText(auth.language, "Live Map", "Live Map")}
          </p>
          <h1 className="page-title">Map-based encroachment review</h1>
          {loadError ? <p className="status-error">{loadError}</p> : null}
        </div>

        <div className="mini-stat-row">
          <div className="mini-stat-card">
            <span>Tracked plots</span>
            <strong>{loading ? "..." : plots.length}</strong>
          </div>
          <div className="mini-stat-card">
            <span>Selected risk</span>
            <strong>{selectedPlot?.risk || "Waiting"}</strong>
          </div>
        </div>
      </section>

      <div className="map-story-stack">
        <Card
          className="map-stage-card map-stage-card-featured"
          eyebrow={getLocalizedText(auth.language, "Field View", "Field View")}
          title="Plot monitoring map"
          action={
            selectedPlot ? (
              <Badge tone={selectedPlot.risk.toLowerCase()}>{selectedPlot.risk}</Badge>
            ) : (
              <span className="map-meta">{loading ? "Loading..." : `${plots.length} plots tracked`}</span>
            )
          }
        >
          <MapView
            onInspectPlot={enrichPlot}
            plots={plots}
            selectedPlotId={selectedPlot?.id}
            onSelectPlot={setSelectedPlotId}
          />
        </Card>

        <div className="map-data-stack">
          <Dashboard auth={auth} data={selectedPlot} />
          <ImagePanel auth={auth} data={selectedPlot} />
        </div>
      </div>
    </div>
  );
}
