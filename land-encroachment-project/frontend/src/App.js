import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { io } from "socket.io-client";

import "./App.css";
import MainLayout from "./layouts/MainLayout";
import {
  SOCKET_URL,
  analyzePlot,
  getAlerts,
  getPlots,
  loginUser,
  registerUser,
  setAuthFailureHandler,
  setAuthToken,
} from "./services/api";
import {
  ROLE_CONFIG,
  getLocalizedText,
  inferChennaiLocality,
} from "./config/appContent";

import Login from "./pages/Login";
import DashboardPage from "./pages/DashboardPage";
import MapPage from "./pages/MapPage";
import AlertsPage from "./pages/AlertsPage";
import PlotDetails from "./pages/PlotDetails";
import AnalyticsPage from "./pages/AnalyticsPage";
import AdminPage from "./pages/AdminPage";
import OwnershipReviewPage from "./pages/OwnershipReviewPage";
import RegistrationVerificationPage from "./pages/RegistrationVerificationPage";

const socket = io(SOCKET_URL, {
  autoConnect: false,
  transports: ["websocket", "polling"],
});

const DEFAULT_AUTH = {
  isAuthenticated: false,
  role: "viewer",
  language: "en",
  theme: "light",
  name: "Guest User",
  username: "",
  token: "",
};

function normalizeRole(role) {
  if (role === "public") {
    return "viewer";
  }
  if (role === "official") {
    return "officer";
  }
  return role || "viewer";
}

function buildPlotRecord(summary = {}, analysis = {}) {
  const plotId = analysis.plot_id || summary.id || "Unknown";
  const change = Number(analysis.change ?? summary.last_change ?? 0);
  const confidence = Number(analysis.confidence ?? 0);
  const risk = analysis.risk || summary.status || "Low";
  const lat = Number(summary.lat ?? analysis.lat ?? 0);
  const lng = Number(summary.lng ?? analysis.lng ?? 0);
  const locationName =
    summary.location_name ||
    analysis.location_name ||
    inferChennaiLocality(lat, lng);
  const area = summary.area || analysis.area || inferChennaiLocality(lat, lng);

  return {
    id: String(plotId),
    plot_id: String(plotId),
    plotName: locationName,
    lat,
    lng,
    area,
    risk,
    status: risk,
    change,
    confidence,
    location_name: locationName,
    survey_no: summary.survey_no || analysis.survey_no || "Survey pending",
    owner_name: summary.owner_name || analysis.owner_name || "Government Land",
    village: summary.village || analysis.village || inferChennaiLocality(lat, lng),
    district: summary.district || analysis.district || "Chennai",
    operator_note:
      summary.operator_note ||
      analysis.operator_note ||
      "Automated change detection active for this monitored parcel.",
    boundary_geojson: analysis.boundary_geojson || summary.boundary_geojson || null,
    image_years: summary.image_years || analysis.image_years || [],
    before_image: analysis.before_image || null,
    after_image: analysis.after_image || null,
    output_image: analysis.output_image || null,
    updatedAt: new Date().toISOString(),
  };
}

function shouldCreateAlert(plot) {
  return plot.risk === "High";
}

function buildAlert(plot, source = "system") {
  return {
    id: `${plot.id}-${Math.round(plot.change * 100)}-${source}`,
    plotId: plot.id,
    plotName: plot.plotName,
    area: plot.area,
    risk: plot.risk,
    change: plot.change,
    confidence: plot.confidence,
    channel: "Mail + Alert Center",
    message: `High-risk encroachment detected at ${plot.plotName} in ${plot.area}.`,
    receivedAt: new Date().toISOString(),
    source,
  };
}

function mergeAlert(existingAlerts, plot, source) {
  if (!shouldCreateAlert(plot)) {
    return existingAlerts;
  }

  const nextAlert = buildAlert(plot, source);
  const alreadyPresent = existingAlerts.some(
    (alert) =>
      alert.plotId === nextAlert.plotId &&
      alert.risk === nextAlert.risk &&
      Math.round(alert.change) === Math.round(nextAlert.change)
  );

  if (alreadyPresent) {
    return existingAlerts;
  }

  return [nextAlert, ...existingAlerts];
}

function mapStoredAlert(alertRow, plotLookup) {
  const relatedPlot = plotLookup.get(String(alertRow.plot_id));
  return {
    id: `stored-${alertRow.id}`,
    plotId: String(alertRow.plot_id),
    plotName:
      relatedPlot?.plotName || relatedPlot?.location_name || `Plot ${alertRow.plot_id}`,
    area: relatedPlot?.area || "Chennai",
    risk: alertRow.risk_level,
    change: Number(relatedPlot?.change ?? 0),
    confidence: Number(relatedPlot?.confidence ?? 0),
    channel: "Mail + Alert Center",
    message: alertRow.message,
    receivedAt: alertRow.created_at,
    source: "database",
    isRead: Boolean(alertRow.is_read),
  };
}

function getStoredAuth() {
  try {
    const raw = localStorage.getItem("lem-session");
    if (!raw) {
      return DEFAULT_AUTH;
    }
    const parsed = JSON.parse(raw);
    return {
      ...DEFAULT_AUTH,
      ...parsed,
      role: normalizeRole(parsed?.role),
      isAuthenticated: Boolean(parsed?.token),
    };
  } catch (error) {
    console.error("Failed to parse auth session", error);
    return DEFAULT_AUTH;
  }
}

function filterPlotsForRole(plots, role) {
  if (role === "viewer") {
    return plots.map((plot) => ({
      ...plot,
      survey_no: "Restricted",
      owner_name: "Government Land",
      operator_note: "Detailed ownership and enforcement notes are restricted.",
      confidence: Math.round(Number(plot.confidence || 0)),
    }));
  }

  return plots;
}

function getDefaultPath(role) {
  return ROLE_CONFIG[role]?.homePath || "/dashboard";
}

function hasAccess(role, path) {
  return ROLE_CONFIG[role]?.allowedPaths.includes(path);
}

function getErrorMessage(error, fallback) {
  return error?.response?.data?.error?.message || fallback;
}

function App() {
  const [plots, setPlots] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedPlotId, setSelectedPlotId] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [auth, setAuth] = useState(() => getStoredAuth());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    localStorage.setItem("lem-session", JSON.stringify(auth));
    document.documentElement.setAttribute("data-theme", auth.theme);
    setAuthToken(auth.token);
  }, [auth]);

  useEffect(() => {
    setAuthFailureHandler((message) => {
      setAuth((current) => ({
        ...current,
        isAuthenticated: false,
        role: "viewer",
        name: DEFAULT_AUTH.name,
        username: "",
        token: "",
      }));
      setLoadError(message || "Your session expired. Please sign in again.");
    });

    return () => {
      setAuthFailureHandler(null);
    };
  }, []);

  useEffect(() => {
    if (!auth.isAuthenticated || !auth.token) {
      socket.disconnect();
      return undefined;
    }

    socket.connect();
    return () => socket.disconnect();
  }, [auth.isAuthenticated, auth.token]);

  async function enrichPlot(plotId) {
    try {
      const analysis = await analyzePlot(String(plotId).split("_")[0]);
      setPlots((currentPlots) =>
        currentPlots.map((plot) =>
          plot.id === String(plotId) ? buildPlotRecord(plot, analysis) : plot
        )
      );
      return analysis;
    } catch (error) {
      console.error(`Failed to analyze plot ${plotId}`, error);
      return null;
    }
  }

  async function loadStoredAlerts(currentPlots) {
    try {
      const response = await getAlerts();
      const rows = response?.data || [];
      const plotLookup = new Map(
        (currentPlots || []).map((plot) => [String(plot.id), plot])
      );
      const persistedAlerts = rows.map((alertRow) =>
        mapStoredAlert(alertRow, plotLookup)
      );
      setAlerts((currentAlerts) => {
        const liveOnlyAlerts = currentAlerts.filter(
          (alert) => alert.source !== "database"
        );
        const merged = [...persistedAlerts];
        liveOnlyAlerts.forEach((alert) => {
          const exists = merged.some(
            (item) =>
              item.plotId === alert.plotId &&
              item.risk === alert.risk &&
              Math.round(Number(item.change || 0)) ===
                Math.round(Number(alert.change || 0))
          );
          if (!exists) {
            merged.unshift(alert);
          }
        });
        return merged;
      });
    } catch (error) {
      console.error("Failed to load persisted alerts", error);
    }
  }

  useEffect(() => {
    let active = true;

    async function loadInitialData() {
      if (!auth.isAuthenticated) {
        setPlots([]);
        setAlerts([]);
        setSelectedPlotId(null);
        setLoadError("");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setLoadError("");
        const response = await getPlots();
        const basePlots = response?.plots || [];

        if (!active) {
          return;
        }

        const mergedPlots = basePlots.map((plot) => buildPlotRecord(plot, {}));
        setPlots(mergedPlots);
        setAlerts([]);
        setSelectedPlotId((current) => current || mergedPlots[0]?.id || null);
        await loadStoredAlerts(mergedPlots);

        basePlots.forEach((plot) => {
          enrichPlot(plot.id);
        });
      } catch (error) {
        if (error?.response?.status === 401 && active) {
          handleLogout();
          setLoadError("Your session expired. Please sign in again.");
        } else if (active) {
          setLoadError(getErrorMessage(error, "Failed to load existing plots from the backend."));
        }
        console.error("Failed to load plots", error);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadInitialData();

    return () => {
      active = false;
    };
  }, [auth.isAuthenticated, auth.token]);

  async function refreshPlots() {
    if (!auth.isAuthenticated) {
      return;
    }

    setLoading(true);
    try {
      setLoadError("");
      const response = await getPlots();
      const basePlots = response?.plots || [];
      const mergedPlots = basePlots.map((plot) => buildPlotRecord(plot, {}));

      setPlots(mergedPlots);
      setAlerts([]);
      setSelectedPlotId((current) => current || mergedPlots[0]?.id || null);
      await loadStoredAlerts(mergedPlots);

      basePlots.forEach((plot) => {
        enrichPlot(plot.id);
      });
    } catch (error) {
      setLoadError(getErrorMessage(error, "Failed to refresh plots from the backend."));
      console.error("Failed to refresh plots", error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    function handlePlotUpdate(message) {
      if (!auth.isAuthenticated) {
        return;
      }

      setPlots((currentPlots) => {
        const existingPlot =
          currentPlots.find((plot) => plot.id === String(message.plot_id)) || {};

        const updatedPlot = buildPlotRecord(existingPlot, message);

        const nextPlots = currentPlots.some(
          (plot) => plot.id === String(message.plot_id)
        )
          ? currentPlots.map((plot) =>
              plot.id === String(message.plot_id) ? updatedPlot : plot
            )
          : [updatedPlot, ...currentPlots];

        setAlerts((currentAlerts) =>
          mergeAlert(currentAlerts, updatedPlot, "live-monitor")
        );

        return nextPlots;
      });
    }

    socket.on("plot_update", handlePlotUpdate);

    return () => {
      socket.off("plot_update", handlePlotUpdate);
    };
  }, [auth.isAuthenticated]);

  const visiblePlots = useMemo(
    () => filterPlotsForRole(plots, auth.role),
    [plots, auth.role]
  );

  const selectedPlot =
    visiblePlots.find((plot) => plot.id === selectedPlotId) || visiblePlots[0] || null;

  const sharedProps = {
    alerts,
    auth,
    enrichPlot,
    loadError,
    loading,
    plots: visiblePlots,
    selectedPlot,
    setSelectedPlotId,
  };

  async function handleLogin({ language, username, password }) {
    try {
      const result = await loginUser({ username, password });
      const user = result?.data?.user || {};
      const token = result?.data?.token || "";

      setAuth((current) => ({
        ...current,
        isAuthenticated: Boolean(token),
        role: normalizeRole(user.role),
        language,
        name: user.full_name || user.username || "Workspace User",
        username: user.username || "",
        token,
      }));

      return {
        ok: true,
        redirectTo: getDefaultPath(normalizeRole(user.role)),
      };
    } catch (error) {
      return {
        ok: false,
        message: getErrorMessage(error, getLocalizedText(language, "Unable to sign in.", "Unable to sign in.")),
      };
    }
  }

  async function handleRegister({ language, fullName, username, password }) {
    try {
      const result = await registerUser({
        full_name: fullName,
        username,
        password,
      });
      const user = result?.data?.user || {};
      const token = result?.data?.token || "";

      setAuth((current) => ({
        ...current,
        isAuthenticated: Boolean(token),
        role: normalizeRole(user.role),
        language,
        name: user.full_name || fullName,
        username: user.username || username,
        token,
      }));

      return {
        ok: true,
        redirectTo: getDefaultPath(normalizeRole(user.role)),
      };
    } catch (error) {
      return {
        ok: false,
        message: getErrorMessage(error, getLocalizedText(language, "Unable to create account.", "Unable to create account.")),
      };
    }
  }

  function handleLogout() {
    setAuth((current) => ({
      ...current,
      isAuthenticated: false,
      role: "viewer",
      name: DEFAULT_AUTH.name,
      username: "",
      token: "",
    }));
  }

  function toggleTheme() {
    setAuth((current) => ({
      ...current,
      theme: current.theme === "dark" ? "light" : "dark",
    }));
  }

  function setLanguage(language) {
    setAuth((current) => ({
      ...current,
      language,
    }));
  }

  function ProtectedRoute({ path, children }) {
    if (!auth.isAuthenticated) {
      return <Navigate to="/" replace />;
    }

    if (!hasAccess(auth.role, path)) {
      return <Navigate to={getDefaultPath(auth.role)} replace />;
    }

    return (
      <MainLayout
        auth={auth}
        onLogout={handleLogout}
        onToggleTheme={toggleTheme}
        onLanguageChange={setLanguage}
      >
        {children}
      </MainLayout>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            auth.isAuthenticated ? (
              <Navigate to={getDefaultPath(auth.role)} replace />
            ) : (
              <Login auth={auth} onLogin={handleLogin} onRegister={handleRegister} />
            )
          }
        />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute path="/dashboard">
              <DashboardPage {...sharedProps} />
            </ProtectedRoute>
          }
        />

        <Route
          path="/map"
          element={
            <ProtectedRoute path="/map">
              <MapPage {...sharedProps} />
            </ProtectedRoute>
          }
        />

        <Route
          path="/alerts"
          element={
            <ProtectedRoute path="/alerts">
              <AlertsPage alerts={alerts} auth={auth} plots={visiblePlots} loading={loading} />
            </ProtectedRoute>
          }
        />

        <Route
          path="/plot-details"
          element={
            <ProtectedRoute path="/plot-details">
              <PlotDetails auth={auth} plots={visiblePlots} loading={loading} />
            </ProtectedRoute>
          }
        />

        <Route
          path="/analytics"
          element={
            <ProtectedRoute path="/analytics">
              <AnalyticsPage auth={auth} plots={visiblePlots} alerts={alerts} loading={loading} />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin"
          element={
            <ProtectedRoute path="/admin">
              <AdminPage
                auth={auth}
                plots={visiblePlots}
                alerts={alerts}
                onUploadSuccess={refreshPlots}
              />
            </ProtectedRoute>
          }
        />

        <Route
          path="/ownership-review"
          element={
            <ProtectedRoute path="/ownership-review">
              <OwnershipReviewPage auth={auth} plots={visiblePlots} />
            </ProtectedRoute>
          }
        />

        <Route
          path="/registration-verification"
          element={
            <ProtectedRoute path="/registration-verification">
              <RegistrationVerificationPage auth={auth} />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
