import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import Sidebar from "../components/Sidebar";
import { ROLE_CONFIG, getLocalizedText } from "../config/appContent";

const PAGE_TITLES = {
  "/dashboard": { en: "Operational Dashboard", ta: "செயல்பாட்டு கட்டுப்பாட்டு பலகம்" },
  "/map": { en: "Live Monitoring Map", ta: "நேரடி கண்காணிப்பு வரைபடம்" },
  "/alerts": { en: "Alert Register", ta: "எச்சரிக்கை பதிவேடு" },
  "/analytics": { en: "Risk Analytics", ta: "ஆபத்து பகுப்பாய்வு" },
  "/plot-details": { en: "Plot Register", ta: "நிலப் பதிவு" },
  "/ownership-review": { en: "Ownership Review", ta: "உரிமை மதிப்பாய்வு" },
  "/admin": { en: "Admin Workspace", ta: "நிர்வாக பணிப்பகுதி" },
};

export default function MainLayout({
  auth,
  children,
  onLanguageChange,
  onLogout,
  onToggleTheme,
}) {
  const location = useLocation();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const title = PAGE_TITLES[location.pathname] || {
    en: "Monitoring Workspace",
    ta: "கண்காணிப்பு பணிப்பகுதி",
  };

  useEffect(() => {
    setIsSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <Sidebar
        auth={auth}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-heading">
            <button
              aria-label="Open menu"
              className="mobile-menu-button"
              onClick={() => setIsSidebarOpen(true)}
              type="button"
            >
              Menu
            </button>
            <div>
              <p className="section-eyebrow">
                {getLocalizedText(
                  auth.language,
                  "Smart Monitoring Control Room",
                  "ஸ்மார்ட் கண்காணிப்பு கட்டுப்பாட்டு அறை"
                )}
              </p>
              <h2 className="topbar-title">
                {auth.language === "ta" ? title.ta : title.en}
              </h2>
            </div>
          </div>

          <div className="topbar-actions">
            <div className="topbar-switches">
              <button className="ghost-button" onClick={onToggleTheme} type="button">
                {auth.theme === "dark"
                  ? getLocalizedText(auth.language, "Light Mode", "ஒளி நிலை")
                  : getLocalizedText(auth.language, "Dark Mode", "இருள் நிலை")}
              </button>
              <button
                className="ghost-button"
                onClick={() => onLanguageChange(auth.language === "ta" ? "en" : "ta")}
                type="button"
              >
                {auth.language === "ta" ? "English" : "தமிழ்"}
              </button>
            </div>

            <div className="topbar-user">
              <span className="topbar-avatar">
                {ROLE_CONFIG[auth.role].label.slice(0, 1)}
              </span>
              <div>
                <strong>{auth.name}</strong>
                <p>{ROLE_CONFIG[auth.role].title}</p>
              </div>
              <button className="ghost-button" onClick={onLogout} type="button">
                {getLocalizedText(auth.language, "Logout", "வெளியேறு")}
              </button>
            </div>
          </div>
        </header>

        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
