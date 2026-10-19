import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { Cancion } from "../types";

interface ContextMenuContextType {
  menuPosition: { x: number; y: number } | null;
  menuSong: Cancion | null;
  infoSong: Cancion | null;
  showMenu: (e: React.MouseEvent | MouseEvent, song: Cancion) => void;
  closeMenu: () => void;
  showInfoModal: (song: Cancion) => void;
  closeInfoModal: () => void;
}

const ContextMenuContext = createContext<ContextMenuContextType | undefined>(undefined);

export function ContextMenuProvider({ children }: { children: ReactNode }) {
  const [menuPosition, setMenuPosition] = useState<{ x: number; y: number } | null>(null);
  const [menuSong, setMenuSong] = useState<Cancion | null>(null);
  const [infoSong, setInfoSong] = useState<Cancion | null>(null);

  const showMenu = useCallback((e: React.MouseEvent | MouseEvent, song: Cancion) => {
    e.preventDefault();
    setMenuPosition({ x: e.clientX, y: e.clientY });
    setMenuSong(song);
  }, []);

  const closeMenu = useCallback(() => {
    setMenuPosition(null);
    setMenuSong(null);
  }, []);

  const showInfoModal = useCallback((song: Cancion) => {
    setInfoSong(song);
    closeMenu();
  }, [closeMenu]);

  const closeInfoModal = useCallback(() => {
    setInfoSong(null);
  }, []);

  return (
    <ContextMenuContext.Provider
      value={{
        menuPosition,
        menuSong,
        infoSong,
        showMenu,
        closeMenu,
        showInfoModal,
        closeInfoModal,
      }}
    >
      {children}
    </ContextMenuContext.Provider>
  );
}

export function useContextMenu() {
  const ctx = useContext(ContextMenuContext);
  if (!ctx) {
    throw new Error("useContextMenu must be used within a ContextMenuProvider");
  }
  return ctx;
}
