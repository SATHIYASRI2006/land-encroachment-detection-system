import { NavLink } from "react-router-dom";

import { ROLE_CONFIG, getLocalizedText } from "../config/appContent";

const links = [
  { to: "/dashboard", en: "Dashboard", ta: "டாஷ்போர்டு" },
  { to: "/map", en: "Map", ta: "வரைபடம்" },
  { to: "/alerts", en: "Alerts", ta: "எச்சரிக்கைகள்" },
  { to: "/analytics", en: "Analytics", ta: "பகுப்பாய்வு" },
  { to: "/plot-details", en: "Plot Details", ta: "நில விவரங்கள்" },
  { to: "/ownership-review", en: "Ownership Review", ta: "உரிமை மதிப்பாய்வு" },
  { to: "/registration-verification", en: "Registration Check", ta: "பதிவு சரிபார்ப்பு" },
  { to: "/admin", en: "Admin Panel", ta: "நிர்வாக பகுதி" },
];

export default function Sidebar({ auth, isOpen = false, onClose }) {
  const allowedLinks = links.filter((link) =>
    ROLE_CONFIG[auth.role].allowedPaths.includes(link.to)
  );

  return (
    <>
      <button
        aria-label="Close menu"
        className={isOpen ? "sidebar-backdrop sidebar-backdrop-visible" : "sidebar-backdrop"}
        onClick={onClose}
        type="button"
      />

      <aside className={isOpen ? "sidebar sidebar-open" : "sidebar"}>
        <div className="sidebar-brand">
          <div className="sidebar-brand-row">
            <p className="sidebar-kicker">
              {getLocalizedText(auth.language, "Secure Monitoring", "பாதுகாப்பான கண்காணிப்பு")}
            </p>
            <button className="sidebar-close" onClick={onClose} type="button">
              x
            </button>
          </div>

          <h1>{getLocalizedText(auth.language, "Land Shield", "நில பாதுகாப்பு")}</h1>
          <span>
            {getLocalizedText(
              auth.language,
              "Chennai Encroachment Intelligence Hub",
              "சென்னை ஆக்கிரமிப்பு நுண்ணறிவு மையம்"
            )}
          </span>
        </div>

        <div className="sidebar-role-card">
          <strong>
            {auth.language === "ta"
              ? ROLE_CONFIG[auth.role].tamilLabel
              : ROLE_CONFIG[auth.role].label}
          </strong>
          <span>{ROLE_CONFIG[auth.role].title}</span>
        </div>

        <nav className="sidebar-nav">
          {allowedLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              onClick={onClose}
              className={({ isActive }) =>
                isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"
              }
            >
              {auth.language === "ta" ? link.ta : link.en}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <p className="sidebar-section-label">
            {getLocalizedText(auth.language, "Industry Features", "தொழில்துறை அம்சங்கள்")}
          </p>
          <span>Geofence watch</span>
          <span>Case workflow</span>
          <span>Audit-ready evidence</span>
        </div>
      </aside>
    </>
  );
}
