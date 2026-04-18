import { NavLink } from "react-router-dom";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/map", label: "Live Map" },
  { to: "/alerts", label: "Alerts" },
  { to: "/analytics", label: "Analytics" },
  { to: "/plot-details", label: "Plot Details" },
  { to: "/admin", label: "Admin Panel" },
];

export default function Navbar() {
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">Smart Monitoring</p>
        <h1 className="brand-title">Land Encroachment Control Room</h1>
      </div>

      <nav className="nav-links">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              isActive ? "nav-link nav-link-active" : "nav-link"
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
