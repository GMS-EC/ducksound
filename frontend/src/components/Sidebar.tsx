import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  House, Heart, FolderTree, List, Compass, Users, Disc3,
  Shield, Search, User,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import SearchDialog from "./SearchDialog";

const iconMap: Record<string, any> = {
  house: House, heart: Heart, folder: FolderTree, list: List,
  compass: Compass, users: Users, disc: Disc3, shield: Shield,
};

const links = [
  { to: "/dashboard", label: "Principal", icon: "house" },
  { to: "/favorites", label: "Favoritos", icon: "heart" },
  { to: "/folders", label: "Carpetas", icon: "folder" },
  { to: "/colecciones", label: "Playlists", icon: "list" },
];

const browseLinks = [
  { to: "/explore", label: "Explorar", icon: "compass" },
  { to: "/artists", label: "Artistas", icon: "users" },
  { to: "/albums", label: "Álbumes", icon: "disc" },
];

export default function Sidebar() {
  const { user } = useAuth();
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <>
      <aside className="sidebar">
        <NavLink to="/dashboard" className="sidebar-logo">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="6" fill="#d95840"/>
            <text x="14" y="20" textAnchor="middle" fill="white" fontSize="16" fontWeight="bold">D</text>
          </svg>
          DuckSound
        </NavLink>

        <div className="sidebar-nav">
          {links.map((l) => {
            const Icon = iconMap[l.icon];
            return (
              <NavLink key={l.to} to={l.to} className={({ isActive }) => "sidebar-nav-link" + (isActive ? " active" : "")}>
                <Icon size={17} />
                {l.label}
              </NavLink>
            );
          })}

          <div className="sidebar-divider" />

          {browseLinks.map((l) => {
            const Icon = iconMap[l.icon];
            return (
              <NavLink key={l.to} to={l.to} className={({ isActive }) => "sidebar-nav-link" + (isActive ? " active" : "")}>
                <Icon size={17} />
                {l.label}
              </NavLink>
            );
          })}

          {user?.role === "admin" && (
            <>
              <div className="sidebar-divider" />
              <NavLink to="/admin" className={({ isActive }) => "sidebar-nav-link" + (isActive ? " active" : "")}>
                <Shield size={17} />
                Admin
              </NavLink>
            </>
          )}
        </div>

        <div className="sidebar-nav" style={{ padding: "8px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          <button onClick={() => setSearchOpen(!searchOpen)} className="sidebar-nav-link" style={{ width: "100%", border: "none", background: "none", textAlign: "left" }}>
            <Search size={17} />
            Buscar
          </button>
          <NavLink to="/profile" className={({ isActive }) => "sidebar-nav-link" + (isActive ? " active" : "")} style={{ width: "100%" }}>
            <User size={17} />
            {user?.nombre_usuario || "Perfil"}
          </NavLink>
        </div>
      </aside>
      <SearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />
    </>
  );
}
