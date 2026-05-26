import { NavLink, Outlet, useNavigate } from "react-router-dom";

const links = [
  { to: "/",            label: "Overview" },
  { to: "/antibiogram", label: "Antibiogram" },
  { to: "/alerts",      label: "Alerts" },
  { to: "/chat",        label: "Stewardship Chat" },
  { to: "/glass",       label: "GLASS Export" },
];

export default function Layout() {
  const navigate = useNavigate();
  const userRaw = localStorage.getItem("amr_user");
  const user = userRaw ? JSON.parse(userRaw) : null;

  const logout = () => {
    localStorage.removeItem("amr_token");
    localStorage.removeItem("amr_user");
    navigate("/login");
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-60 bg-sentinel-700 text-white flex flex-col">
        <div className="p-6 text-2xl font-semibold tracking-tight">
          AMR Sentinel
        </div>
        <nav className="flex-1 px-2 space-y-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                `block px-4 py-2 rounded text-sm ${
                  isActive ? "bg-sentinel-500" : "hover:bg-sentinel-500/60"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 text-xs border-t border-white/10">
          {user && (
            <>
              <div className="font-medium">{user.name}</div>
              <div className="opacity-70">{user.facility_id} · {user.role}</div>
            </>
          )}
          <button
            onClick={logout}
            className="mt-2 text-xs underline opacity-80 hover:opacity-100"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
