import { usePlayer } from "../contexts/PlayerContext";

export default function Equalizer() {
  const { playing } = usePlayer();
  return (
    <div className={`playing-eq ${playing ? "" : "paused"}`}>
      <span></span>
      <span></span>
      <span></span>
      <span></span>
    </div>
  );
}
