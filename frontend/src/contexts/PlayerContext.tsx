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
  playbackRate: number;
  play: (songs?: Cancion[], index?: number) => void;
  pause: () => void;
  resume: () => void;
  togglePlay: () => void;
  next: () => void;
  prev: () => void;
  seek: (time: number) => void;
  setVolume: (v: number) => void;
  setPlaybackRate: (rate: number) => void;
  toggleMute: () => void;
  toggleShuffle: () => void;
  toggleRepeat: () => void;
  addToQueue: (songs: Cancion[]) => void;
}

const PlayerContext = createContext<PlayerContextType | undefined>(undefined);

export function PlayerProvider({ children }: { children: ReactNode }) {
  const [queue, setQueue] = useState<Cancion[]>(() => {
    try {
      const saved = localStorage.getItem('ducksound:queue');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [currentIndex, setCurrentIndex] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('ducksound:currentIndex');
      return saved ? parseInt(saved, 10) : -1;
    } catch {
      return -1;
    }
  });
  const [playing, setPlaying] = useState(false);
  const [volume, setVolumeState] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('ducksound:volume');
      return saved ? parseFloat(saved) : 0.7;
    } catch {
      return 0.7;
    }
  });
  const [muted, setMuted] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('ducksound:muted');
      return saved === 'true';
    } catch {
      return false;
    }
  });
  const [shuffle, setShuffle] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('ducksound:shuffle');
      return saved === 'true';
    } catch {
      return false;
    }
  });
  const [repeat, setRepeat] = useState<'none' | 'one' | 'all'>(() => {
    try {
      const saved = localStorage.getItem('ducksound:repeat');
      if (saved === 'none' || saved === 'one' || saved === 'all') return saved;
      return 'none';
    } catch {
      return 'none';
    }
  });
  const [currentTime, setCurrentTime] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('ducksound:currentTime');
      return saved ? parseFloat(saved) : 0;
    } catch {
      return 0;
    }
  });
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRateState] = useState<number>(1.0);
  const playbackRateRef = useRef(1.0);

  useEffect(() => {
    playbackRateRef.current = playbackRate;
  }, [playbackRate]);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const prevVolumeRef = useRef(volume);

  const initialTimeRef = useRef<number>(0);
  const hasInitializedTime = useRef(false);
  if (!hasInitializedTime.current) {
    try {
      const saved = localStorage.getItem('ducksound:currentTime');
      initialTimeRef.current = saved ? parseFloat(saved) : 0;
    } catch {
      initialTimeRef.current = 0;
    }
    hasInitializedTime.current = true;
  }

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

  // Sync state to localStorage
  useEffect(() => {
    localStorage.setItem('ducksound:queue', JSON.stringify(queue));
  }, [queue]);

  useEffect(() => {
    localStorage.setItem('ducksound:currentIndex', currentIndex.toString());
  }, [currentIndex]);

  useEffect(() => {
    localStorage.setItem('ducksound:volume', volume.toString());
  }, [volume]);

  useEffect(() => {
    localStorage.setItem('ducksound:muted', muted.toString());
  }, [muted]);

  useEffect(() => {
    localStorage.setItem('ducksound:shuffle', shuffle.toString());
  }, [shuffle]);

  useEffect(() => {
    localStorage.setItem('ducksound:repeat', repeat);
  }, [repeat]);

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

      // Reset currentTime on song transition
      localStorage.setItem('ducksound:currentTime', '0');
      initialTimeRef.current = 0;
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
      }
      setCurrentTime(0);
    }
  }, []);

  const playPrev = useCallback(() => {
    const audio = audioRef.current;
    if (audio && audio.currentTime > 3) {
      audio.currentTime = 0;
      setCurrentTime(0);
      localStorage.setItem('ducksound:currentTime', '0');
      initialTimeRef.current = 0;
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

      // Reset currentTime on song transition
      localStorage.setItem('ducksound:currentTime', '0');
      initialTimeRef.current = 0;
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
      }
      setCurrentTime(0);
    }
  }, []);

  // Audio lifecycle & event listeners
  useEffect(() => {
    const audio = new Audio();
    audio.preload = 'metadata';
    try {
      const savedMuted = localStorage.getItem('ducksound:muted') === 'true';
      const savedVolume = localStorage.getItem('ducksound:volume');
      const initialVol = savedVolume ? parseFloat(savedVolume) : 0.7;
      audio.volume = savedMuted ? 0 : initialVol;
    } catch {
      audio.volume = 0.7;
    }
    audioRef.current = audio;

    let lastSavedTime = -1;
    const onTimeUpdate = () => {
      const time = audio.currentTime;
      setCurrentTime(time);
      const roundedTime = Math.floor(time);
      if (roundedTime !== lastSavedTime) {
        try {
          localStorage.setItem('ducksound:currentTime', time.toString());
          lastSavedTime = roundedTime;
        } catch {
          // ignore
        }
      }
    };
    const onDurationChange = () => setDuration(audio.duration || 0);
    const onLoadedMetadata = () => {
      setDuration(audio.duration || 0);
      audio.playbackRate = playbackRateRef.current;
      if (initialTimeRef.current > 0) {
        audio.currentTime = initialTimeRef.current;
        setCurrentTime(initialTimeRef.current);
        initialTimeRef.current = 0;
      }
    };
    const onEnded = () => {
      if (repeatRef.current === 'one') {
        audio.currentTime = 0;
        localStorage.setItem('ducksound:currentTime', '0');
        initialTimeRef.current = 0;
        setCurrentTime(0);
        audio.play().catch(console.error);
      } else {
        playNext();
      }
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('durationchange', onDurationChange);
    audio.addEventListener('loadedmetadata', onLoadedMetadata);
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('durationchange', onDurationChange);
      audio.removeEventListener('loadedmetadata', onLoadedMetadata);
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

      audio.playbackRate = playbackRate;

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
  }, [currentSong, playing, playbackRate]);

  const play = useCallback((songs?: Cancion[], index?: number) => {
    if (songs && songs.length > 0) {
      const idx = typeof index === 'number' ? index : 0;
      setQueue(songs);
      setCurrentIndex(idx);
      setPlaying(true);

      // Reset currentTime
      localStorage.setItem('ducksound:currentTime', '0');
      initialTimeRef.current = 0;
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
      }
      setCurrentTime(0);
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

  const setPlaybackRate = useCallback((rate: number) => {
    setPlaybackRateState(rate);
    const audio = audioRef.current;
    if (audio) {
      audio.playbackRate = rate;
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

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in input, textarea, select, or contenteditable
      const activeEl = document.activeElement;
      const tag = activeEl?.tagName;
      if (
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        activeEl?.getAttribute('contenteditable') === 'true'
      ) {
        return;
      }

      switch (e.key) {
        case ' ':
          e.preventDefault();
          togglePlay();
          break;
        case 'ArrowRight':
          e.preventDefault();
          if (e.ctrlKey) {
            playNext();
          } else if (audioRef.current) {
            seek(Math.min(audioRef.current.duration || 0, audioRef.current.currentTime + 10));
          }
          break;
        case 'ArrowLeft':
          e.preventDefault();
          if (e.ctrlKey) {
            playPrev();
          } else if (audioRef.current) {
            seek(Math.max(0, audioRef.current.currentTime - 10));
          }
          break;
        case 'ArrowUp':
          e.preventDefault();
          if (audioRef.current) {
            const newVol = Math.min(1.0, audioRef.current.volume + 0.05);
            setVolume(newVol);
          }
          break;
        case 'ArrowDown':
          e.preventDefault();
          if (audioRef.current) {
            const newVol = Math.max(0.0, audioRef.current.volume - 0.05);
            setVolume(newVol);
          }
          break;
        case 'm':
        case 'M':
          e.preventDefault();
          toggleMute();
          break;
        case 's':
        case 'S':
          e.preventDefault();
          toggleShuffle();
          break;
        case 'r':
        case 'R':
          e.preventDefault();
          toggleRepeat();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePlay, seek, playNext, playPrev, setVolume, toggleMute, toggleShuffle, toggleRepeat]);

  return (
    <PlayerContext.Provider value={{
      queue, currentIndex, currentSong, playing, volume, muted,
      shuffle, repeat, currentTime, duration, playbackRate,
      play, pause, resume, togglePlay, next: playNext, prev: playPrev, seek,
      setVolume, setPlaybackRate, toggleMute, toggleShuffle, toggleRepeat, addToQueue,
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
