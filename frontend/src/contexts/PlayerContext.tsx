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

  // Refs for tracking mutable states in event listeners & callbacks
  const queueRef = useRef<Cancion[]>([]);
  const currentIndexRef = useRef(-1);
  const playingRef = useRef(false);
  const repeatRef = useRef<'none' | 'one' | 'all'>('none');
  const shuffleRef = useRef(false);

  // Sync refs with states
  useEffect(() => { queueRef.current = queue; }, [queue]);
  useEffect(() => { currentIndexRef.current = currentIndex; }, [currentIndex]);
  useEffect(() => { playingRef.current = playing; }, [playing]);
  useEffect(() => { repeatRef.current = repeat; }, [repeat]);
  useEffect(() => { shuffleRef.current = shuffle; }, [shuffle]);

  const playNext = useCallback(() => {
    const q = queueRef.current;
    const idx = currentIndexRef.current;
    const rep = repeatRef.current;
    const shuf = shuffleRef.current;
    const len = q.length;

    if (len === 0) return;

    let nextIdx = idx + 1;
    if (shuf) {
      nextIdx = Math.floor(Math.random() * len);
    } else if (nextIdx >= len) {
      nextIdx = rep === 'all' ? 0 : len - 1;
    }

    if (nextIdx >= 0 && nextIdx < len) {
      setCurrentIndex(nextIdx);
      setPlaying(true);
    }
  }, []);

  const playPrev = useCallback(() => {
    const audio = audioRef.current;
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0;
      setCurrentTime(0);
      return;
    }

    const q = queueRef.current;
    const idx = currentIndexRef.current;
    const rep = repeatRef.current;
    const shuf = shuffleRef.current;
    const len = q.length;

    if (len === 0) return;

    let prevIdx = idx - 1;
    if (shuf) {
      prevIdx = Math.floor(Math.random() * len);
    } else if (prevIdx < 0) {
      prevIdx = rep === 'all' ? len - 1 : 0;
    }

    if (prevIdx >= 0 && prevIdx < len) {
      setCurrentIndex(prevIdx);
      setPlaying(true);
    }
  }, []);

  // Audio lifecycle & event listeners
  useEffect(() => {
    const audio = new Audio();
    audio.preload = 'metadata';
    audioRef.current = audio;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onDurationChange = () => setDuration(audio.duration || 0);
    const onEnded = () => {
      if (repeatRef.current === 'one') {
        audio.currentTime = 0;
        audio.play().catch(console.error);
      } else {
        playNext();
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
  }, [playNext]);

  const currentSong = currentIndex >= 0 && currentIndex < queue.length ? queue[currentIndex] : null;

  // React dynamically to currentSong and playing state changes
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (currentSong) {
      const audioUrl = `/audio/${currentSong.id}`;
      const absoluteAudioUrl = window.location.origin + audioUrl;
      
      if (audio.src !== absoluteAudioUrl) {
        audio.src = audioUrl;
        audio.load();
      }

      if (playing) {
        audio.play().catch((err) => {
          console.error("Audio playback failed:", err);
          setPlaying(false);
        });
      } else {
        audio.pause();
      }
    } else {
      audio.pause();
      audio.src = '';
    }
  }, [currentSong, playing]);

  const play = useCallback((songs?: Cancion[], index?: number) => {
    if (songs && songs.length > 0) {
      const idx = typeof index === 'number' ? index : 0;
      setQueue(songs);
      setCurrentIndex(idx);
      setPlaying(true);
    } else {
      const q = queueRef.current;
      const idx = currentIndexRef.current;
      if (q.length > 0 && idx >= 0) {
        setPlaying(true);
      }
    }
  }, []);

  const pause = useCallback(() => {
    setPlaying(false);
  }, []);

  const resume = useCallback(() => {
    setPlaying(true);
  }, []);

  const togglePlay = useCallback(() => {
    setPlaying((p) => !p);
  }, []);

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

  return (
    <PlayerContext.Provider value={{
      queue, currentIndex, currentSong, playing, volume, muted,
      shuffle, repeat, currentTime, duration,
      play, pause, resume, togglePlay, next: playNext, prev: playPrev, seek,
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
