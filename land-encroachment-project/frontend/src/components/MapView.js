import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { COLORS, getRiskColor } from "../theme/colors";

function toLeafletLatLngs(boundaryGeojson) {
  const ring = boundaryGeojson?.coordinates?.[0];
  if (!Array.isArray(ring)) {
    return [];
  }
  return ring.map(([lng, lat]) => [lat, lng]);
}

function getPolygonCenter(latLngs) {
  if (!latLngs.length) {
    return null;
  }
  const sums = latLngs.reduce(
    (acc, [lat, lng]) => ({ lat: acc.lat + lat, lng: acc.lng + lng }),
    { lat: 0, lng: 0 }
  );
  return [sums.lat / latLngs.length, sums.lng / latLngs.length];
}

export default function MapView({
  plots,
  selectedPlotId,
  onInspectPlot,
  onSelectPlot,
}) {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const layerRef = useRef(null);
  const frameRef = useRef(null);
  const legendRef = useRef(null);

  useEffect(() => {
    if (mapInstance.current) {
      return;
    }

    mapInstance.current = L.map(mapRef.current, {
      zoomControl: true,
    }).setView([13.0827, 80.2707], 12);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(mapInstance.current);

    layerRef.current = L.layerGroup().addTo(mapInstance.current);

    legendRef.current = L.control({ position: "bottomleft" });
    legendRef.current.onAdd = () => {
      const div = L.DomUtil.create("div", "map-legend");
      div.innerHTML = `
        <strong>Risk Legend</strong>
        <span><i style="background:${COLORS.riskHigh}"></i>High</span>
        <span><i style="background:${COLORS.riskMedium}"></i>Medium</span>
        <span><i style="background:${COLORS.riskLow}"></i>Low</span>
      `;
      return div;
    };
    legendRef.current.addTo(mapInstance.current);

    return () => {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
      if (mapInstance.current) {
        mapInstance.current.off();
        mapInstance.current.remove();
        mapInstance.current = null;
      }
      layerRef.current = null;
      legendRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapInstance.current;
    const layer = layerRef.current;
    if (!map || !layer) {
      return;
    }

    if (frameRef.current) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }

    layer.clearLayers();
    const polygonLayers = [];

    plots.forEach((plot) => {
      const latLngs = toLeafletLatLngs(plot.boundary_geojson);
      if (!latLngs.length) {
        return;
      }

      const riskColor = getRiskColor(plot.risk);
      const isSelected = plot.id === selectedPlotId;
      const polygon = L.polygon(latLngs, {
        color: riskColor,
        weight: isSelected ? 5 : 2.5,
        fillColor: riskColor,
        fillOpacity: isSelected ? 0.38 : 0.18,
      });

      const center = getPolygonCenter(latLngs);
      if (center) {
        const marker = L.circleMarker(center, {
          radius: isSelected ? 8 : 5,
          weight: 2,
          color: "#ffffff",
          fillColor: riskColor,
          fillOpacity: 1,
        });
        marker.bindTooltip(plot.plotName, {
          direction: "top",
          offset: [0, -8],
          opacity: 0.9,
        });
        marker.on("click", () => {
          onSelectPlot?.(plot.id);
          onInspectPlot?.(plot.id);
        });
        layer.addLayer(marker);
      }

      polygon.bindPopup(`
        <div style="font-family: Segoe UI, Arial, sans-serif; color: ${COLORS.text}; min-width: 180px;">
          <strong>${plot.plotName}</strong><br/>
          Risk: ${plot.risk}<br/>
          Change: ${Number(plot.change || 0).toFixed(2)}%<br/>
          Confidence: ${Number(plot.confidence || 0).toFixed(2)}%<br/>
          Area: ${plot.area}
        </div>
      `);

      polygon.on("click", () => {
        onSelectPlot?.(plot.id);
        onInspectPlot?.(plot.id);
      });

      polygon.on("mouseover", () => {
        polygon.setStyle({
          fillOpacity: 0.42,
          weight: isSelected ? 5 : 3.5,
        });
      });

      polygon.on("mouseout", () => {
        polygon.setStyle({
          fillOpacity: isSelected ? 0.38 : 0.18,
          weight: isSelected ? 5 : 2.5,
        });
      });

      layer.addLayer(polygon);
      polygonLayers.push(polygon);
    });

    const focusedPlot = plots.find((plot) => plot.id === selectedPlotId);
    const focusedLatLngs = toLeafletLatLngs(focusedPlot?.boundary_geojson);
    frameRef.current = requestAnimationFrame(() => {
      if (!mapInstance.current || !mapRef.current) {
        return;
      }

      map.invalidateSize({ pan: false, animate: false });

      if (focusedLatLngs.length) {
        map.fitBounds(focusedLatLngs, {
          padding: [42, 42],
          maxZoom: 16,
          animate: false,
        });
        return;
      }

      if (polygonLayers.length) {
        const group = L.featureGroup(polygonLayers);
        map.fitBounds(group.getBounds(), {
          padding: [42, 42],
          maxZoom: 14,
          animate: false,
        });
      }
    });

    return () => {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [plots, selectedPlotId, onSelectPlot, onInspectPlot]);

  return <div ref={mapRef} className="map-canvas map-canvas-featured" />;
}
