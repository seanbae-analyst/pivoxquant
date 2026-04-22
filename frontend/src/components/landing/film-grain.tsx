"use client";

/**
 * FilmGrain — SVG fractalNoise overlay for Hero backgrounds.
 * -----------------------------------------------------------
 * Pure CSS/SVG (no JS, no GSAP). Sits above the dot pattern and spotlight,
 * below content. Uses mix-blend-mode: overlay at opacity 0.03 — just enough
 * to break up flat Vantablack without being visible as grain.
 *
 * Safe on mobile: ~1.2KB inline SVG, no animation frames.
 */

type Props = {
  opacity?: number;
  blendMode?: "overlay" | "soft-light" | "multiply";
};

export function FilmGrain({ opacity = 0.035, blendMode = "overlay" }: Props) {
  // Inline SVG — baseFrequency ~0.9 gives a fine film-grain texture.
  // colorMatrix desaturates to ivory-tinted monochrome so it never reads purple.
  const svg =
    `<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'>` +
    `<filter id='n'>` +
    `<feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/>` +
    `<feColorMatrix values='0 0 0 0 0.96  0 0 0 0 0.94  0 0 0 0 0.91  0 0 0 0.55 0'/>` +
    `</filter>` +
    `<rect width='100%' height='100%' filter='url(%23n)'/>` +
    `</svg>`;

  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0"
      style={{
        backgroundImage: `url("data:image/svg+xml;utf8,${svg}")`,
        mixBlendMode: blendMode,
        opacity,
      }}
    />
  );
}

export default FilmGrain;
