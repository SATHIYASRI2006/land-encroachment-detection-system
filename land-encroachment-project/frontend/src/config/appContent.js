export const ROLE_CONFIG = {
  viewer: {
    key: "viewer",
    label: "Citizen",
    tamilLabel: "Citizen",
    title: "Citizen Workspace",
    homePath: "/dashboard",
    allowedPaths: ["/dashboard", "/map", "/alerts", "/plot-details"],
  },
  officer: {
    key: "officer",
    label: "Official",
    tamilLabel: "Official",
    title: "Field and Revenue Officer",
    homePath: "/map",
    allowedPaths: [
      "/dashboard",
      "/map",
      "/alerts",
      "/analytics",
      "/plot-details",
      "/ownership-review",
      "/registration-verification",
    ],
  },
  admin: {
    key: "admin",
    label: "Admin",
    tamilLabel: "Admin",
    title: "State Monitoring Admin",
    homePath: "/admin",
    allowedPaths: [
      "/dashboard",
      "/map",
      "/alerts",
      "/analytics",
      "/plot-details",
      "/admin",
      "/ownership-review",
      "/registration-verification",
    ],
  },
};

export const PLACE_PRESETS = [
  { key: "north-west", label: "Madhavaram", latMin: 13.08, lngMax: 80.24 },
  { key: "north-east", label: "Ennore Creek", latMin: 13.08, lngMin: 80.24 },
  { key: "central-west", label: "Anna Nagar", latMin: 13.045, lngMax: 80.235 },
  { key: "central-east", label: "Tondiarpet", latMin: 13.045, lngMin: 80.235 },
  { key: "south-west", label: "Guindy", latMin: 13.01, lngMax: 80.24 },
  { key: "south-east", label: "Pallikaranai", latMin: 13.01, lngMin: 80.24 },
  { key: "coastal-south", label: "Thiruvanmiyur", latMin: 0, lngMin: 80.275 },
];

export function inferChennaiLocality(lat, lng) {
  const latitude = Number(lat);
  const longitude = Number(lng);

  if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
    return "Chennai";
  }

  const match = PLACE_PRESETS.find((item) => {
    const latPass = item.latMin === undefined || latitude >= item.latMin;
    const lngMinPass = item.lngMin === undefined || longitude >= item.lngMin;
    const lngMaxPass = item.lngMax === undefined || longitude <= item.lngMax;
    return latPass && lngMinPass && lngMaxPass;
  });

  return match?.label || "Adyar";
}

export function getRoleInsights(role, plots = [], alerts = []) {
  const highRisk = plots.filter((plot) => plot.risk === "High").length;
  const mediumRisk = plots.filter((plot) => plot.risk === "Medium").length;
  const publicSafePlots = plots.filter((plot) => plot.risk !== "High").length;

  if (role === "admin") {
    return [
      { label: "Audit trail coverage", value: "98%", tone: "info" },
      { label: "Auto refresh health", value: "Online", tone: "low" },
      { label: "Pending approvals", value: String(Math.max(highRisk - 1, 0)), tone: "medium" },
      { label: "Open escalations", value: String(alerts.length), tone: "high" },
    ];
  }

  if (role === "officer") {
    return [
      { label: "Priority inspections", value: String(highRisk), tone: "high" },
      { label: "Watchlist plots", value: String(mediumRisk), tone: "medium" },
      { label: "Field SLA", value: "4 hrs", tone: "info" },
      { label: "Case sync", value: "Synced", tone: "low" },
    ];
  }

  return [
    { label: "Public-safe plots", value: String(publicSafePlots), tone: "low" },
    { label: "Verified alerts", value: String(alerts.length), tone: "medium" },
    { label: "Helpline", value: "1913", tone: "info" },
    { label: "Tamil support", value: "Enabled", tone: "low" },
  ];
}

export function getRoleDescription(role) {
  if (role === "admin") {
    return "Full access to uploads, governance settings, compliance tracking, and monitoring operations.";
  }
  if (role === "officer") {
    return "Operational view for field verification, alert handling, and evidence-led decision making.";
  }
  return "Public-friendly view with simplified labels, safe summaries, and grievance-ready information.";
}

export function getLocalizedText(language, english, tamil) {
  return language === "ta" ? tamil : english;
}
