import { COLORS, getRiskColor } from "../theme/colors";

export default function Badge({ children, tone = "neutral" }) {
  const palette = getPalette(tone);

  return (
    <span
      className="ui-badge"
      style={{
        backgroundColor: palette.background,
        color: palette.color,
        borderColor: palette.border,
      }}
    >
      {children}
    </span>
  );
}

function getPalette(tone) {
  if (tone === "critical") {
    return {
      background: "rgba(183, 28, 28, 0.10)",
      color: COLORS.riskCritical,
      border: "rgba(183, 28, 28, 0.2)",
    };
  }
  if (tone === "high") {
    return {
      background: "rgba(229, 57, 53, 0.10)",
      color: COLORS.riskHigh,
      border: "rgba(229, 57, 53, 0.2)",
    };
  }
  if (tone === "medium" || tone === "warning") {
    return {
      background: "rgba(251, 140, 0, 0.10)",
      color: COLORS.riskMedium,
      border: "rgba(251, 140, 0, 0.2)",
    };
  }
  if (tone === "low" || tone === "success") {
    return {
      background: "rgba(76, 175, 80, 0.10)",
      color: COLORS.riskLow,
      border: "rgba(76, 175, 80, 0.2)",
    };
  }
  if (tone === "info") {
    return {
      background: "rgba(30, 58, 138, 0.08)",
      color: COLORS.primary,
      border: "rgba(30, 58, 138, 0.18)",
    };
  }

  return {
    background: "rgba(15, 23, 42, 0.04)",
    color: getRiskColor(tone),
    border: "rgba(102, 112, 133, 0.18)",
  };
}
