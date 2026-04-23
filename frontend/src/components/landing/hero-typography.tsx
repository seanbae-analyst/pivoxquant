"use client";

/**
 * HeroTypography — LCP-safe glyph-by-glyph reveal for the hero H1.
 * -----------------------------------------------------------------------
 * Strategy
 *   1. SSR / first paint: renders the H1 as *plain text* — one <span>
 *      with the whole phrase. This is the LCP element; Lighthouse counts
 *      it the instant the browser paints.
 *   2. After hydration + first idle + viewport entry, we mount a second
 *      layer of per-glyph spans on top (absolute, same typography),
 *      fade the static layer out, and stagger-fade the glyphs in.
 *
 *   The visible text is identical, so SEO readers see exactly what users
 *   see, and the static → glyph handoff is imperceptible (~80 ms).
 *
 * "learns" word
 *   We keep the existing .pq-cfo-word class so the bronze glow keyframe
 *   from globals.css still fires. The glyph split wraps each character
 *   but the word span still carries the class.
 *
 * Reduced motion
 *   All timing collapses to 0; the static layer stays visible.
 */

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";

type Segment = {
  text: string;
  /** italic + .pq-cfo-word (bronze glow) */
  cfo?: boolean;
  /** insert an actual <br /> after this segment */
  br?: boolean;
};

type Props = {
  id?: string;
  className?: string;
  segments: Segment[];
  /** ms after mount before the glyph layer takes over. Default 700. */
  startDelayMs?: number;
};

/* Splits a segment into individual glyph entries. Spaces stay as
 * non-breaking spaces so the width of the static + animated layers
 * match exactly (critical for the cross-fade to be invisible). */
function splitSegment(seg: Segment, segIdx: number) {
  return Array.from(seg.text).map((ch, i) => ({
    ch: ch === " " ? "\u00A0" : ch,
    key: `s${segIdx}-g${i}`,
    cfo: seg.cfo === true,
  }));
}

export function HeroTypography({
  id,
  className,
  segments,
  startDelayMs = 700,
}: Props) {
  const reduceMotion = useReducedMotion();
  const [glyphsOn, setGlyphsOn] = useState(false);
  const rootRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (reduceMotion) return;
    const el = rootRef.current;
    if (!el) return;

    let triggered = false;
    let timer: number | undefined;

    const trigger = () => {
      if (triggered) return;
      triggered = true;
      timer = window.setTimeout(() => setGlyphsOn(true), startDelayMs);
    };

    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            trigger();
            io.disconnect();
          }
        }
      },
      { threshold: 0.15 },
    );
    io.observe(el);

    // Safety net: if the H1 is above the fold, IO can fire synchronously
    // but some browsers wait a frame. Trigger on next idle regardless.
    const idle =
      (window as Window & { requestIdleCallback?: (cb: () => void) => number })
        .requestIdleCallback ?? ((cb: () => void) => setTimeout(cb, 50));
    const idleId = idle(trigger);

    return () => {
      io.disconnect();
      if (timer) window.clearTimeout(timer);
      void idleId; // best-effort; cancelIdleCallback varies
    };
  }, [reduceMotion, startDelayMs]);

  // Flat list of glyphs for staggering (index → delay).
  const glyphs = segments.flatMap((seg, i) => splitSegment(seg, i));

  return (
    <h1 id={id} ref={rootRef} className={className}>
      {/* Static layer — the LCP text. Cross-fades out once glyphs on. */}
      <span
        aria-hidden={glyphsOn ? "true" : undefined}
        className="pq-hero-h1-static"
        style={{
          opacity: glyphsOn && !reduceMotion ? 0 : 1,
          transition: reduceMotion
            ? "none"
            : "opacity 320ms cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        {segments.map((seg, i) => {
          const body = seg.cfo ? (
            <span
              key={`stat-${i}`}
              className={reduceMotion ? "" : "pq-cfo-word"}
              style={{
                fontStyle: "italic",
                ...(reduceMotion ? { color: "var(--pq-bronze-light)" } : {}),
              }}
            >
              {seg.text}
            </span>
          ) : (
            <span key={`stat-${i}`}>{seg.text}</span>
          );
          return (
            <span key={`stat-wrap-${i}`}>
              {body}
              {seg.br ? <br /> : null}
            </span>
          );
        })}
      </span>

      {/* Glyph layer — only painted after hydration + viewport entry.
          Absolute-positioned over the static layer, identical metrics. */}
      {!reduceMotion && (
        <span
          aria-hidden="true"
          className="pq-hero-h1-glyphs"
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            opacity: glyphsOn ? 1 : 0,
          }}
        >
          {segments.map((seg, segIdx) => {
            const segGlyphs = splitSegment(seg, segIdx);
            // Compute the starting index within the full glyph stream so
            // the stagger timing runs continuously across segments.
            const startGlyphIndex = glyphs.findIndex(
              (g) => g.key === segGlyphs[0]?.key,
            );
            const block = (
              <span
                key={`glyph-wrap-${segIdx}`}
                className={seg.cfo ? "pq-cfo-word" : undefined}
                style={seg.cfo ? { fontStyle: "italic" } : undefined}
              >
                {segGlyphs.map((g, i) => (
                  <motion.span
                    key={g.key}
                    initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
                    animate={
                      glyphsOn
                        ? { opacity: 1, y: 0, filter: "blur(0px)" }
                        : { opacity: 0, y: 14, filter: "blur(6px)" }
                    }
                    transition={{
                      duration: 0.45,
                      ease: [0.16, 1, 0.3, 1],
                      delay: (startGlyphIndex + i) * 0.04,
                    }}
                    style={{ display: "inline-block", whiteSpace: "pre" }}
                  >
                    {g.ch}
                  </motion.span>
                ))}
              </span>
            );
            return (
              <span key={`glyph-seg-${segIdx}`}>
                {block}
                {seg.br ? <br /> : null}
              </span>
            );
          })}
        </span>
      )}
    </h1>
  );
}

export default HeroTypography;
