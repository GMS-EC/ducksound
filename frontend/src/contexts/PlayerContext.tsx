import {
  createContext, useContext, useState, useRef, useCallback,
  useEffect, type ReactNode,
} from 'react';
import type { Cancion } from '../types';

interface PlayerContextType {
  queue: Cancion[];
  currentIndex: number;
  currentSong: Cancion | null;
  playing: boolean;
  volume: number;
  muted: boolean;
  shuffle: boolean;
  repeat: 'none' | 'one' | 'all';
  currentTime: number;
  duration: number;
  play: (songs?: Cancion[], index?: number) => void;
  pause: () => void;
  resume: () => void;
  togglePlay: () => void;
  next: () => void;
  prev: () => void;
  seek: (time: number) => void;
  setVolume: (v: number) => void;
  toggleMute: () => void;
  toggleShuffle: () => void;
  toggleRepeat: () => void;
  addToQueue: (songs: Cancion[]) => void;
}

const PlayerContext = createContext<PlayerContextType | undefined>(undefined);

export function PlayerProvider({ children }: { children: ReactNode }) {
  const [queue, setQueue] = useState<Cancion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [volume, setVolumeState] = useState(0.7);
  const [muted, setMuted] = useState(false);
  const [shuffle, setShuffle] = useState(false);
  const [repeat, setRepeat] = useState<'none' | 'one' | 'all'>('none');
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const prevVolumeRef = useRef(0.7);

  useEffect(() => {
    const audio = new Audio();
    audio.preload = 'metadata';
    audioRef.current = audio;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onDurationChange = () => setDuration(audio.duration || 0);
    const onEnded = () => {
      if (repeat === 'one') {
        audio.currentTime = 0;
        audio.play();
      } else {
        next();
      }
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('durationchange', onDurationChange);
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('durationchange', onDurationChange);
      audio.removeEventListener('ended', onEnded);
      audio.pause();
      audio.src = '';
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

// removed || 'http://localhost:8604';

  const loadSong = useCallback((index: number) => {
    const audio = audioRef.current;
    if (!audio || index < 0 || index >= queue.length) return;
    setCurrentIndex(index);
    const song = queue[index];
    const audioUrl = `/audio/${song.id}`;
    audio.src = audioUrl;
    audio.load();
    audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    setCurrentTime(0);
  }, [queue]);

  const play = useCallback((songs?: Cancion[], index?: number) => {
    if (songs) {
      setQueue(typeof index === 'number' ? songs : songs);
      const i = typeof index === 'number' ? index : 0;
      // Use setTimeout to let state update
      setTimeout(() => loadSong(i), 0);
    } else if (queue.length > 0 && currentIndex >= 0) {
      audioRef.current?.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  }, [queue, currentIndex, loadSong]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
    setPlaying(false);
  }, []);

  const resume = useCallback(() => {
    audioRef.current?.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
  }, []);

  const togglePlay = useCallback(() => {
    if (playing) pause();
    else resume();
  }, [playing, pause, resume]);

  const getNextIndex = useCallback((current: number, dir: 1 | -1): number => {
    const len = queue.length;
    if (len === 0) return -1;
    if (shuffle) return Math.floor(Math.random() * len);
    let next = current + dir;
    if (next < 0) next = repeat === 'all' ? len - 1 : 0;
    if (next >= len) next = repeat === 'all' ? 0 : len - 1;
    return next;
  }, [queue.length, shuffle, repeat]);

  const next = useCallback(() => {
    const idx = getNextIndex(currentIndex, 1);
    if (idx >= 0 && idx < queue.length) loadSong(idx);
  }, [currentIndex, getNextIndex, queue.length, loadSong]);

  const prev = useCallback(() => {
    const audio = audioRef.current;
    // If more than 3 seconds in, restart current song
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    const idx = getNextIndex(currentIndex, -1);
    if (idx >= 0 && idx < queue.length) loadSong(idx);
  }, [currentIndex, getNextIndex, queue.length, loadSong]);

  const seek = useCallback((time: number) => {
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = time;
      setCurrentTime(time);
    }
  }, []);

  const setVolume = useCallback((v: number) => {
    const audio = audioRef.current;
    if (audio) {
      audio.volume = v;
      setVolumeState(v);
    }
    if (v > 0) {
      setMuted(false);
      prevVolumeRef.current = v;
    }
  }, []);

  const toggleMute = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (muted) {
      audio.volume = prevVolumeRef.current;
      setVolumeState(prevVolumeRef.current);
      setMuted(false);
    } else {
      prevVolumeRef.current = volume;
      audio.volume = 0;
      setVolumeState(0);
      setMuted(true);
    }
  }, [muted, volume]);

  const toggleShuffle = useCallback(() => setShuffle((s) => !s), []);
  const toggleRepeat = useCallback(() => {
    setRepeat((r) => r === 'none' ? 'all' : r === 'all' ? 'one' : 'none');
  }, []);

  const addToQueue = useCallback((songs: Cancion[]) => {
    setQueue((prev) => [...prev, ...songs]);
  }, []);

  const currentSong = currentIndex >= 0 && currentIndex < queue.length ? queue[currentIndex] : null;

  return (
    <PlayerContext.Provider value={{
      queue, currentIndex, currentSong, playing, volume, muted,
      shuffle, repeat, currentTime, duration,
      play, pause, resume, togglePlay, next, prev, seek,
      setVolume, toggleMute, toggleShuffle, toggleRepeat, addToQueue,
    }}>
      {children}
    </PlayerContext.Provider>
  );
}

export function usePlayer() {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider');
  return ctx;
}
