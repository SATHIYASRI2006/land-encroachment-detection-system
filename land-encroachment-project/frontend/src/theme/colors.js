export const COLORS = {
  primary: "#1E3A8A",
  secondary: "#00897B",
  background: "#F0F0F0",
  text: "#212121",
  mapLandGreen: "#2E7D32",
  mapTerrainBrown: "#6D4C41",
  riskLow: "#4CAF50",
  riskMedium: "#FACC15",
  riskHigh: "#E53935",
  riskCritical: "#B71C1C",
  white: "#FFFFFF",
  border: "#D7DBE7",
  muted: "#667085",
  surface: "#FFFFFF",
  surfaceSoft: "#F8FAFC",
  sidebar: "#132A63",
  shadow: "0 12px 30px rgba(30, 58, 138, 0.12)",
};

export function getRiskColor(risk) {
  if (risk === "Critical") return COLORS.riskCritical;
  if (risk === "High") return COLORS.riskHigh;
  if (risk === "Medium" || risk === "Suspicious") return COLORS.riskMedium;
  return COLORS.riskLow;
}
