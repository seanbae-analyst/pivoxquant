"use client";

/**
 * HeroParticles — slow drifting ivory motes + editorial glyphs.
 * -----------------------------------------------------------------------
 * Canvas 2D, ~36 particles. Each is one of:
 *   • dot        — 1px ivory @ 0.12 alpha (majority)
 *   • ring       — 3-4px hollow circle (bronze @ 0.10)
 *   • square     — 2.5px outlined square (ivory @ 0.08)
 *   • plus/math  — tiny "+" glyph (bronze @ 0.11)
 *
 * Motion
 *   • Drift velocity 0.10 – 0.28 px / frame (≈ 6 – 17 px / s at 60 fps).
 *   • Lifespan 7–14 s with a 0.6 s in-fade and 1 s out-fade.
 *   • On death, respawn at a random edge point with a fresh direction.
 *
 * Performance
 *   • Uses a single canvas, one RAF loop.
 *   • IntersectionObserver pauses the RAF when the hero is off-screen.
 *   • DevicePixelRatio clamped to 2 — avoids 4× cost on retina zoom.
 *   • `prefers-reduced-motion` → renders the particles once, statically.
 *
 * A11y: decorative, `aria-hidden`, `role="presentation"`.
 */

import { useEffect, useRef } from "react";
import { useReducedMotion } from "motion/react";

type Kind = "dot" | "ring" | "square" | "plus";

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  kind: Kind;
  life: number; // seconds lived
  ttl: number; // total lifespan
};

const IVORY = "245, 240, 232";
const BRONZE = "184, 149, 106";
const COUNT_DESKTOP = 44;
const COUNT_MOBILE = 22;

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function pickKind(): Kind {
  const r = Math.random();
  if (r < 0.68) return "dot";
  if (r < 0.82) return "ring";
  if (r < 0.93) return "plus";
  return "square";
}

function spawn(w: number, h: number): Particle {
  // Spawn just off a random edge so particles "enter" the frame.
  const edge = Math.floor(Math.random() * 4);
  let x = rand(0, w);
  let y = rand(0, h);
  if (edge === 0) y = -8;
  else if (edge === 1) x = w + 8;
  else if (edge === 2) y = h + 8;
  else x = -8;

  const speed = rand(0.1, 0.28);
  const angle = rand(0, Math.PI * 2);
  const kind = pickKind();
  const size = kind === "dot" ? rand(0.7, 1.2) : rand(2.2, 3.6);

  return {
    x,
    y,
    vx: Math.cos(angle) * speed,
    vy: Math.sin(angle) * speed,
    size,
    kind,
    life: 0,
    ttl: rand(7, 14),
  };
}

function drawParticle(
  ctx: CanvasRenderingContext2D,
  p: Particle,
  dpr: number,
) {
  // Envelope — fade in 0.6s, full, fade out 1.0s.
  let alpha = 1;
  if (p.life < 0.6) alpha = p.life / 0.6;
  else if (p.ttl - p.life < 1.0) alpha = Math.max(0, (p.ttl - p.life) / 1.0);

  const x = p.x * dpr;
  const y = p.y * dpr;
  const s = p.size * dpr;

  switch (p.kind) {
    case "dot":
      ctx.fillStyle = `rgba(${IVORY}, ${0.12 * alpha})`;
      ctx.beginPath();
      ctx.arc(x, y, s * 0.5, 0, Math.PI * 2);
      ctx.fill();
      break;
    case "ring":
      ctx.strokeStyle = `rgba(${BRONZE}, ${0.14 * alpha})`;
      ctx.lineWidth = Math.max(1, dpr * 0.75);
      ctx.beginPath();
      ctx.arc(x, y, s, 0, Math.PI * 2);
      ctx.stroke();
      break;
    case "square":
      ctx.strokeStyle = `rgba(${IVORY}, ${0.10 * alpha})`;
      ctx.lineWidth = Math.max(1, dpr * 0.7);
      ctx.strokeRect(x - s / 2, y - s / 2, s, s);
      break;
    case "plus": {
      ctx.strokeStyle = `rgba(${BRONZE}, ${0.16 * alpha})`;
      ctx.lineWidth = Math.max(1, dpr * 0.8);
      ctx.beginPath();
      ctx.moveTo(x - s * 0.7, y);
      ctx.lineTo(x + s * 0.7, y);
      ctx.moveTo(x, y - s * 0.7);
      ctx.lineTo(x, y + s * 0.7);
      ctx.stroke();
      break;
    }
  }
}

export function HeroParticles({ className }: { className?: string }) {
  const reduceMotion = useReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    let w = 0;
    let h = 0;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    let particles: Particle[] = [];
    let raf = 0;
    let last = performance.now();
    let running = true;

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      const rect = parent.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;

      const count = w < 720 ? COUNT_MOBILE : COUNT_DESKTOP;
      particles = Array.from({ length: count }, () => {
        const p = spawn(w, h);
        // Pre-seed life so we don't get a global fade-in on first frame.
        p.life = Math.random() * p.ttl;
        p.x = Math.random() * w;
        p.y = Math.random() * h;
        return p;
      });
    };

    const step = (now: number) => {
      raf = 0;
      if (!running) return;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.life += dt;

        // Wrap + respawn: also recycle if the particle wandered way off.
        if (p.life >= p.ttl || p.x < -20 || p.x > w + 20 || p.y < -20 || p.y > h + 20) {
          particles[i] = spawn(w, h);
          continue;
        }

        drawParticle(ctx, p, dpr);
      }

      raf = requestAnimationFrame(step);
    };

    // Draw a single static frame (reduced-motion or initial paint).
    const drawStatic = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const p of particles) drawParticle(ctx, p, dpr);
    };

    resize();
    if (reduceMotion) {
      drawStatic();
    } else {
      raf = requestAnimationFrame(step);
    }

    // Resize listener — debounced via rAF.
    let resizePending = false;
    const onResize = () => {
      if (resizePending) return;
      resizePending = true;
      requestAnimationFrame(() => {
        resizePending = false;
        resize();
        if (reduceMotion) drawStatic();
      });
    };
    window.addEventListener("resize", onResize);

    // Pause when off-screen.
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const visible = e.isIntersecting;
          if (visible && !running) {
            running = true;
            last = performance.now();
            if (!reduceMotion && !raf) raf = requestAnimationFrame(step);
          } else if (!visible && running) {
            running = false;
            if (raf) cancelAnimationFrame(raf);
            raf = 0;
          }
        }
      },
      { threshold: 0 },
    );
    io.observe(canvas);

    return () => {
      running = false;
      if (raf) cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      io.disconnect();
    };
  }, [reduceMotion]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      role="presentation"
      className={`pointer-events-none absolute inset-0 z-[1] ${className ?? ""}`}
    />
  );
}

export default HeroParticles;
