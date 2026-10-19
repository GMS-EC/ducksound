import { useEffect, useRef } from "react";

interface VisualizerTabProps {
  playing: boolean;
}

export default function VisualizerTab({ playing }: VisualizerTabProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationRef = useRef<number | null>(null);
  const stateRef = useRef({
    heights: Array.from({ length: 32 }, () => 0),
    targetHeights: Array.from({ length: 32 }, () => 0),
    phase: 0,
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Handle resizing dynamically
    const resizeCanvas = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (rect) {
        canvas.width = rect.width;
        canvas.height = Math.max(300, rect.height - 40); // Leave some margin
      }
    };

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    // Animation Loop
    const draw = () => {
      if (!ctx || !canvas) return;

      const w = canvas.width;
      const h = canvas.height;

      // Clear with solid background
      ctx.fillStyle = "#222229";
      ctx.fillRect(0, 0, w, h);

      const state = stateRef.current;
      state.phase += playing ? 0.05 : 0.01;

      // Calculate Target Heights based on sine waves to simulate audio spectrum
      if (playing) {
        for (let i = 0; i < 32; i++) {
          // Combination of different sine frequencies to look organic and rhythmic
          const value1 = Math.sin(state.phase + i * 0.15) * 0.4 + 0.5;
          const value2 = Math.cos(state.phase * 1.8 - i * 0.25) * 0.3 + 0.3;
          const noise = Math.random() * 0.2; // Add high-frequency jitter
          state.targetHeights[i] = Math.max(10, (value1 + value2 + noise) * h * 0.8);
        }
      } else {
        // Smoothly fade target heights to flat lines when paused
        for (let i = 0; i < 32; i++) {
          state.targetHeights[i] = Math.max(2, state.targetHeights[i] * 0.9);
        }
      }

      // Smooth current heights towards target heights (LERP)
      for (let i = 0; i < 32; i++) {
        state.heights[i] += (state.targetHeights[i] - state.heights[i]) * 0.2;
      }

      // Draw Wave Background (aesthetic subtle lines)
      ctx.strokeStyle = "#30201d";
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let x = 0; x < w; x++) {
        const y = h * 0.55 + Math.sin(state.phase + x * 0.02) * (playing ? 25 : 4) +
                  Math.cos(state.phase * 0.5 + x * 0.01) * (playing ? 15 : 2);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Draw Spectrum Bars
      const barCount = 32;
      const gap = 4;
      const totalGapsWidth = gap * (barCount - 1);
      const barWidth = (w - 24 - totalGapsWidth) / barCount; // 12px margin on sides
      
      const startX = 12;

      for (let i = 0; i < barCount; i++) {
        const barHeight = state.heights[i];
        const x = startX + i * (barWidth + gap);
        const y = h - 20 - barHeight;

        // Draw solid premium gradient for each bar (no alpha transparency)
        const gradient = ctx.createLinearGradient(x, h - 20, x, y);
        gradient.addColorStop(0, "#30201d"); // Dark Rust
        gradient.addColorStop(0.5, "#d95840"); // DuckSound Accent Orange
        gradient.addColorStop(1, "#f06a50"); // Bright Orange Tip

        ctx.fillStyle = gradient;
        
        // Draw round-capped bars
        ctx.beginPath();
        if (ctx.roundRect) {
          ctx.roundRect(x, y, barWidth, barHeight, [4, 4, 0, 0]);
        } else {
          ctx.rect(x, y, barWidth, barHeight);
        }
        ctx.fill();
      }

      // Draw Floor line
      ctx.fillStyle = "#2a2a33";
      ctx.fillRect(12, h - 20, w - 24, 2);

      animationRef.current = requestAnimationFrame(draw);
    };

    animationRef.current = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener("resize", resizeCanvas);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [playing]);

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "16px 0 0" }}>
      <canvas
        ref={canvasRef}
        style={{
          width: "100%",
          display: "block",
          borderRadius: 8,
          background: "#222229",
        }}
      />
      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 8, fontWeight: 500, letterSpacing: "0.05em", textTransform: "uppercase" }}>
        {playing ? "Visualizando Espectro" : "Audio Pausado"}
      </div>
    </div>
  );
}
