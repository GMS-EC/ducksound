export interface User {
  id: number;
  nombre_usuario: string;
  nombre_publico: string | null;
  role: 'admin' | 'user';
  idioma_preferido: string;
  audio_quality: 'lossless' | 'high' | 'standard' | 'saver';
  crossfade_enabled: boolean;
  activity_tracking: boolean;
  display_name?: string;
}

export interface Session {
  success: boolean;
  user: User;
  session_token: string;
}

export interface Artista {
  id: number;
  nombre: string;
  nombre_normalizado: string | null;
  musicbrainz_id: string | null;
  foto_url: string | null;
  biografia: string | null;
  fecha_creacion: string;
}

export interface Album {
  id: number;
  titulo: string;
  anio: number | null;
  portada_url: string | null;
  artista_id: number;
  musicbrainz_id: string | null;
}

export interface Cancion {
  id: number;
  titulo: string;
  artista: string | null;
  album: string | null;
  duracion: number | null;
  ruta_audio: string;
  ruta_lrc: string | null;
  ruta_imagen: string | null;
  genero: string | null;
  sample_rate: number | null;
  bit_depth: number | null;
  channels: number | null;
  nyquist_freq: number | null;
  dynamic_range: number | null;
  peak_level: number | null;
  rms_level: number | null;
  total_samples: number | null;
  bit_rate: number | null;
  numero_pista?: number | null;
  numero_disco?: number | null;
}

export interface DailyMix {
  id: number;
  usuario_id: number;
  nombre: string;
  fecha: string;
  fecha_creacion: string;
  canciones: Cancion[];
}

export interface Coleccion {
  id: number;
  nombre: string;
  descripcion: string | null;
  portada_url: string | null;
  usuario_id: number;
  fecha_creacion: string;
}

export interface DashboardStats {
  canciones: number;
  albumes: number;
  artistas: number;
  mixes: number;
}

export interface TopSong {
  cancion: Cancion;
  plays: number;
}

export interface TopArtist {
  artista: Artista;
  plays: number;
}

export interface TopGenre {
  genero: string | null;
  plays: number;
}

export interface UserStats {
  usuario: User;
  is_admin: boolean;
  top_songs: TopSong[];
  top_artists: { nombre: string; id: number; plays: number }[];
  total_plays: number;
  total_hours: number;
  last_24h: number;
}

export interface AlbumData {
  album: Album;
  cover_url: string | null;
  track_count: number;
  total_duration?: number;
}

export interface ArtistData {
  artist: Artista;
  album_count: number;
  song_count: number;
  cover_url: string | null;
}

export interface AlbumDetail {
  album: Album;
  discos: {
    disc_num: number;
    songs: Cancion[];
  }[];
  cover_url: string | null;
  total_duration: number;
  track_count: number;
}

export interface SearchResult {
  songs: Array<Cancion & { audio: string; cover: string; lyrics: string }>;
  artists: Array<Artista & { foto: string }>;
  albums: Array<Album & { artista: string }>;
}
