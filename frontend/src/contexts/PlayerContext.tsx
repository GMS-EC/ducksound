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
  const queueRef = useRef<Cancion[]>([]);
  const currentIndexRef = useRef(-1);
  const shuffleRef = useRef(false);
  const repeatRef = useRef<'none' | 'one' | 'all'>('none');

  useEffect(() => { queueRef.current = queue; }, [queue]);
  useEffect(() => { currentIndexRef.current = currentIndex; }, [currentIndex]);
  useEffect(() => { shuffleRef.current = shuffle; }, [shuffle]);
  useEffect(() => { repeatRef.current = repeat; }, [repeat]);

  const playSongFromQueue = useCallback((songs: Cancion[], index: number) => {
    const audio = audioRef.current;
    if (!audio || index < 0 || index >= songs.length) return;

    const song = songs[index];
    queueRef.current = songs;
    currentIndexRef.current = index;
    setQueue(songs);
    setCurrentIndex(index);
    setCurrentTime(0);
    setDuration(0);

    audio.src = `/audio/${song.id}`;
    audio.load();
    audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
  }, []);

  const getNextIndexFrom = useCallback((songs: Cancion[], current: number, dir: 1 | -1): number => {
    const len = songs.length;
    if (len === 0) return -1;
    if (shuffleRef.current) return Math.floor(Math.random() * len);
    let target = current + dir;
    if (target < 0) return repeatRef.current === 'all' ? len - 1 : 0;
    if (target >= len) return repeatRef.current === 'all' ? 0 : len - 1;
    return target;
  }, []);

  useEffect(() => {
    const audio = new Audio();
    audio.preload = 'metadata';
    audio.volume = prevVolumeRef.current;
    audioRef.current = audio;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onDurationChange = () => setDuration(audio.duration || 0);
    const onEnded = () => {
      if (repeatRef.current === 'one') {
        audio.currentTime = 0;
        audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
      } else {
        const songs = queueRef.current;
        const idx = getNextIndexFrom(songs, currentIndexRef.current, 1);
        if (idx !== currentIndexRef.current || repeatRef.current === 'all') {
          playSongFromQueue(songs, idx);
        } else {
          setPlaying(false);
        }
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
  }, [getNextIndexFrom, playSongFromQueue]);

// removed || 'http://localhost:8604';

  const play = useCallback((songs?: Cancion[], index?: number) => {
    if (songs) {
      const i = typeof index === 'number' ? index : 0;
      playSongFromQueue(songs, i);
    } else if (queue.length > 0 && currentIndex >= 0) {
      audioRef.current?.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  }, [queue.length, currentIndex, playSongFromQueue]);

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

  const next = useCallback(() => {
    const songs = queueRef.current;
    const idx = getNextIndexFrom(songs, currentIndexRef.current, 1);
    if (idx >= 0 && idx < songs.length) playSongFromQueue(songs, idx);
  }, [getNextIndexFrom, playSongFromQueue]);

  const prev = useCallback(() => {
    const audio = audioRef.current;
    // If more than 3 seconds in, restart current song
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    const songs = queueRef.current;
    const idx = getNextIndexFrom(songs, currentIndexRef.current, -1);
    if (idx >= 0 && idx < songs.length) playSongFromQueue(songs, idx);
  }, [getNextIndexFrom, playSongFromQueue]);

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
    setQueue((prev) => {
      const nextQueue = [...prev, ...songs];
      queueRef.current = nextQueue;
      return nextQueue;
    });
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
