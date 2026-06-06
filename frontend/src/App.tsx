import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext";
import Sidebar from "./components/Sidebar";
import PlayerBar from "./components/PlayerBar";
import RightPanel from "./components/RightPanel";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ExplorePage from "./pages/ExplorePage";
import FavoritesPage from "./pages/FavoritesPage";
import FoldersPage from "./pages/FoldersPage";
import ColeccionesPage from "./pages/ColeccionesPage";
import AdminPage from "./pages/AdminPage";
import ArtistDetailPage from "./pages/ArtistDetailPage";
import AlbumDetailPage from "./pages/AlbumDetailPage";
import ArtistsPage from "./pages/ArtistsPage";
import AlbumsPage from "./pages/AlbumsPage";
import ColeccionDetailPage from "./pages/ColeccionDetailPage";
import ProfilePage from "./pages/ProfilePage";

function AppContent() {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/explore" element={<ExplorePage />} />
            <Route path="/artists" element={<ArtistsPage />} />
            <Route path="/albums" element={<AlbumsPage />} />
            <Route path="/favorites" element={<FavoritesPage />} />
            <Route path="/folders" element={<FoldersPage />} />
            <Route path="/colecciones" element={<ColeccionesPage />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/artist/:id" element={<ArtistDetailPage />} />
            <Route path="/album/:id" element={<AlbumDetailPage />} />
            <Route path="/coleccion/:id" element={<ColeccionDetailPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
        <RightPanel />
      </div>
      <PlayerBar />
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "#1a1a1f" }}>
        <div style={{ color: "#9ca3af" }}>Cargando...</div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return <AppContent />;
}
