"use client";

/**
 * ReportFlipCard — individual flip card for /features/reports.
 *
 * Front: report metadata (title, cadence, page count, excerpt, Open PDF link)
 * Back: editorial sample-page preview (excerpt from published template)
 *
 * Flip triggers:
 *   • Hover (pointer: fine)
 *   • Focus (keyboard)
 *   • Click / Enter / Space toggle (explicit flip, persists until re-toggled)
 *
 * Respects prefers-reduced-motion: when reduced, no 3D rotation —
 * only opacity cross-fade. Keyboard and click still work.
 *
 * No hardcoded tickers. Sample previews are neutral ("Example Portfolio",
 * page-text extracted from template cadence language).
 */

import Link from "next/link";
import { useId, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight, FileText, RotateCcw } from "lucide-react";

export type FlipSample = {
  name: string;
  subtitle: string;
  excerpt: string;
  href: string;
  pageCount: string;      // Spine tag e.g. "5 pages"
  cadence: string;        // e.g. "Monday briefing"
  preview: {
    kicker: string;       // Editorial kicker on back
    heading: string;      // Back heading
    lede: string;         // Lead paragraph
    bullets: readonly string[]; // 3 observation lines
    closer: string;       // Italic closer
  };
};

const EASE_FLIP: [number, number, number, number] = [0.65, 0, 0.35, 1];

function CardChrome({
  side,
  hidden,
  children,
}: {
  side: "front" | "back";
  /**
   * True when this face is currently rotated away from the viewer.
   * We set aria-hidden so assistive tech skips it, and descendants
   * individually use tabIndex={-1} (see FrontFace / BackFace) — Tab
   * would otherwise walk into the hidden face's buttons / links even
   * though backface-visibility hides them visually.
   */
  hidden: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      aria-hidden={hidden || undefined}
      className="absolute inset-0 flex flex-col overflow-hidden rounded-sm p-7"
      style={{
        // Opaque backgrounds on both faces — any alpha here was the
        // root cause of the hover-flash (#FAF8F3 leaked through during
        // the first few frames of rotateY).
        backgroundColor: side === "front" ? "#0D0D0D" : "#FAF8F3",
        border:
          side === "front"
            ? "0.5px solid rgba(184,149,106,0.25)"
            : "1px solid rgba(139,111,71,0.38)",
        // 3D face stacking — hide the rotated-away face completely.
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
        // Promote to its own GPU layer so the first rotateY frame
        // doesn't flash an untextured composite (white on most GPUs).
        willChange: "transform",
        transform:
          side === "back"
            ? "rotateY(180deg) translateZ(0)"
            : "translateZ(0)",
        transformOrigin: "center center",
        boxShadow:
          side === "back"
            ? "inset 0 0 0 1px rgba(255,255,255,0.35)"
            : undefined,
      }}
    >
      {children}
    </div>
  );
}

function FrontFace({
  s,
  onFlip,
  flipped,
  hidden,
}: {
  s: FlipSample;
  onFlip: () => void;
  flipped: boolean;
  /** True when the card is flipped — front face is rotated away. */
  hidden: boolean;
}) {
  // When the face is rotated away, every interactive descendant is pulled
  // out of the tab order so Tab doesn't land on an invisible button.
  const interactiveTabIndex = hidden ? -1 : 0;
  return (
    <CardChrome side="front" hidden={hidden}>
      {/* Hover hairline */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 transition-opacity duration-500 group-hover:opacity-100 group-focus-within:opacity-100"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(184,149,106,0.5) 50%, transparent 100%)",
        }}
      />

      <div className="flex items-start justify-between">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-sm"
          style={{
            backgroundColor: "rgba(184,149,106,0.1)",
            border: "0.5px solid rgba(184,149,106,0.3)",
            color: "var(--pq-bronze)",
          }}
        >
          <FileText className="h-4 w-4" aria-hidden />
        </div>
        <span
          className="font-serif uppercase"
          style={{
            color: "rgba(184,149,106,0.7)",
            fontSize: "12px",
            letterSpacing: "0.22em",
          }}
        >
          {s.pageCount}
        </span>
      </div>

      <div className="mt-5">
        <h3
          className="font-serif"
          style={{
            color: "var(--pq-ivory)",
            fontSize: "20px",
            fontWeight: 500,
            letterSpacing: "-0.01em",
            marginBottom: 6,
          }}
        >
          {s.name}
        </h3>
        <p
          className="font-serif italic"
          style={{
            color: "rgba(184,149,106,0.85)",
            fontSize: "12px",
          }}
        >
          {s.subtitle}
        </p>
      </div>

      <p
        className="mt-4 font-serif"
        style={{
          color: "rgba(245,240,232,0.68)",
          fontSize: "14px",
          lineHeight: 1.6,
        }}
      >
        {s.excerpt}
      </p>

      <div className="mt-auto flex items-center justify-between pt-5">
        <Link
          href={s.href}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          tabIndex={interactiveTabIndex}
          aria-hidden={hidden || undefined}
          className="inline-flex items-center gap-1.5 font-serif italic"
          style={{
            color: "var(--pq-bronze)",
            fontSize: "14px",
            borderBottom: "0.5px solid rgba(184,149,106,0.4)",
            paddingBottom: 2,
          }}
        >
          Open PDF
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onFlip();
          }}
          tabIndex={interactiveTabIndex}
          aria-hidden={hidden || undefined}
          aria-pressed={flipped}
          aria-label={`Preview ${s.name} sample page`}
          className="inline-flex items-center gap-1.5 font-serif uppercase transition-opacity hover:opacity-100"
          style={{
            color: "rgba(184,149,106,0.7)",
            fontSize: "12px",
            letterSpacing: "0.22em",
            opacity: 0.85,
          }}
        >
          Flip to preview
          <RotateCcw className="h-3 w-3" aria-hidden />
        </button>
      </div>
    </CardChrome>
  );
}

function BackFace({
  s,
  onFlip,
  hidden,
}: {
  s: FlipSample;
  onFlip: () => void;
  /** True when the card is showing the front — back face is rotated away. */
  hidden: boolean;
}) {
  const interactiveTabIndex = hidden ? -1 : 0;
  return (
    <CardChrome side="back" hidden={hidden}>
      {/* Bronze inner hairline frame */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-[10px] rounded-[3px]"
        style={{ border: "0.5px solid rgba(139, 111, 71, 0.32)" }}
      />

      {/* Paper grain overlay */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-sm"
        style={{
          backgroundImage:
            "radial-gradient(circle at 50% 50%, rgba(139, 111, 71, 0.04) 0%, transparent 65%), repeating-linear-gradient(0deg, rgba(10,10,10,0.012) 0px, rgba(10,10,10,0.012) 1px, transparent 1px, transparent 3px)",
          mixBlendMode: "multiply",
        }}
      />

      <div className="relative z-10 flex items-start justify-between">
        <span
          className="font-serif uppercase"
          style={{
            color: "rgba(111, 86, 54, 0.95)",
            fontSize: "12px",
            letterSpacing: "0.22em",
          }}
        >
          {s.preview.kicker}
        </span>
        <span
          className="font-serif italic"
          style={{
            color: "rgba(111, 86, 54, 0.7)",
            fontSize: "12px",
          }}
        >
          {s.cadence}
        </span>
      </div>

      <h4
        className="relative z-10 mt-4 font-serif italic"
        style={{
          color: "#2A1F13",
          fontSize: "18px",
          fontWeight: 400,
          lineHeight: 1.15,
          letterSpacing: "-0.01em",
        }}
      >
        {s.preview.heading}
      </h4>

      <p
        className="relative z-10 mt-3 font-serif"
        style={{
          color: "rgba(42,31,19,0.78)",
          fontSize: "14px",
          lineHeight: 1.55,
        }}
      >
        {s.preview.lede}
      </p>

      <ul className="relative z-10 mt-3 flex flex-col gap-1.5">
        {s.preview.bullets.map((b) => (
          <li
            key={b}
            className="font-serif"
            style={{
              color: "rgba(42,31,19,0.72)",
              fontSize: "12px",
              lineHeight: 1.5,
              paddingLeft: 10,
              position: "relative",
            }}
          >
            <span
              aria-hidden
              style={{
                position: "absolute",
                left: 0,
                top: 7,
                width: 4,
                height: 1,
                backgroundColor: "rgba(111,86,54,0.7)",
              }}
            />
            {b}
          </li>
        ))}
      </ul>

      <div className="relative z-10 mt-auto flex items-end justify-between pt-4">
        <p
          className="font-serif italic"
          style={{
            color: "rgba(42,31,19,0.6)",
            fontSize: "12px",
            lineHeight: 1.45,
            maxWidth: "20ch",
          }}
        >
          {s.preview.closer}
        </p>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onFlip();
          }}
          tabIndex={interactiveTabIndex}
          aria-hidden={hidden || undefined}
          aria-label={`Flip back to ${s.name} overview`}
          className="inline-flex items-center gap-1.5 font-serif uppercase"
          style={{
            color: "rgba(111, 86, 54, 0.85)",
            fontSize: "12px",
            letterSpacing: "0.22em",
          }}
        >
          <RotateCcw className="h-3 w-3" aria-hidden />
          Back
        </button>
      </div>
    </CardChrome>
  );
}

export default function ReportFlipCard({ s }: { s: FlipSample }) {
  const reduce = useReducedMotion();
  const [flipped, setFlipped] = useState(false);
  const [hovered, setHovered] = useState(false);
  const uid = useId();

  const showBack = flipped || hovered;

  const toggle = () => setFlipped((v) => !v);

  // Keyboard — Enter / Space flip
  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggle();
    }
  };

  // Reduced motion: no rotateY, opacity cross-fade instead.
  if (reduce) {
    return (
      <div
        className="group relative"
        style={{ minHeight: 320 }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <div
          role="button"
          tabIndex={0}
          aria-pressed={flipped}
          aria-label={`${s.name} — ${flipped ? "sample preview" : "overview"}`}
          aria-describedby={uid}
          onKeyDown={onKeyDown}
          onClick={toggle}
          className="relative h-full w-full"
          style={{ minHeight: 320 }}
        >
          <motion.div
            animate={{ opacity: showBack ? 0 : 1 }}
            transition={{ duration: 0.35 }}
            className="absolute inset-0"
            style={{ pointerEvents: showBack ? "none" : "auto" }}
            aria-hidden={showBack || undefined}
          >
            <div
              className="absolute inset-0 flex flex-col overflow-hidden rounded-sm p-7"
              style={{
                backgroundColor: "#0D0D0D",
                border: "0.5px solid rgba(184,149,106,0.25)",
              }}
            >
              <FrontFaceContent
                s={s}
                onFlip={toggle}
                flipped={flipped}
                hidden={showBack}
              />
            </div>
          </motion.div>
          <motion.div
            animate={{ opacity: showBack ? 1 : 0 }}
            transition={{ duration: 0.35 }}
            className="absolute inset-0"
            style={{ pointerEvents: showBack ? "auto" : "none" }}
            aria-hidden={!showBack || undefined}
          >
            <div
              className="absolute inset-0 flex flex-col overflow-hidden rounded-sm p-7"
              style={{
                backgroundColor: "#FAF8F3",
                border: "1px solid rgba(139,111,71,0.38)",
              }}
            >
              <BackFaceContent s={s} onFlip={toggle} hidden={!showBack} />
            </div>
          </motion.div>
        </div>
        <span id={uid} className="sr-only">
          Press Enter or Space to flip between overview and sample preview.
        </span>
      </div>
    );
  }

  // 3D flip (default)
  return (
    <div
      className="group relative"
      style={{
        perspective: "1400px",
        minHeight: 320,
        // Force a separate stacking context so the rotating card's
        // compositor layer can't blend with siblings mid-hover.
        isolation: "isolate",
        // Prevent any clipped white container behind the card from
        // appearing through the front face on GPUs that composite
        // perspective layers against the document background.
        backgroundColor: "#050505",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        role="button"
        tabIndex={0}
        aria-pressed={flipped}
        aria-label={`${s.name} — ${flipped ? "sample preview" : "overview"}`}
        aria-describedby={uid}
        onKeyDown={onKeyDown}
        onClick={toggle}
        className="relative h-full w-full cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-[var(--pq-bronze)] focus-visible:ring-offset-2 focus-visible:ring-offset-[#050505]"
        style={{ minHeight: 320 }}
      >
        <motion.div
          animate={{ rotateY: showBack ? 180 : 0 }}
          transition={{ duration: 0.75, ease: EASE_FLIP }}
          className="relative h-full w-full"
          style={{
            transformStyle: "preserve-3d",
            minHeight: 320,
            // Promote the rotator to its own layer up-front so the very
            // first frame is already GPU-composited — eliminates the
            // 1-2 frame white flash at hover start.
            willChange: "transform",
            WebkitTransformStyle: "preserve-3d",
          }}
        >
          <FrontFace
            s={s}
            onFlip={toggle}
            flipped={flipped}
            hidden={showBack}
          />
          <BackFace s={s} onFlip={toggle} hidden={!showBack} />
        </motion.div>
      </div>
      <span id={uid} className="sr-only">
        Press Enter or Space to flip between overview and sample preview.
      </span>
    </div>
  );
}

// Split content so reduced-motion branch can render without backface tricks.
function FrontFaceContent({
  s,
  onFlip,
  flipped,
  hidden,
}: {
  s: FlipSample;
  onFlip: () => void;
  flipped: boolean;
  /** True when the front is faded out — keyboard must not land here. */
  hidden: boolean;
}) {
  const interactiveTabIndex = hidden ? -1 : 0;
  return (
    <>
      <div className="flex items-start justify-between">
        <div
          className="flex h-9 w-9 items-center justify-center rounded-sm"
          style={{
            backgroundColor: "rgba(184,149,106,0.1)",
            border: "0.5px solid rgba(184,149,106,0.3)",
            color: "var(--pq-bronze)",
          }}
        >
          <FileText className="h-4 w-4" aria-hidden />
        </div>
        <span
          className="font-serif uppercase"
          style={{
            color: "rgba(184,149,106,0.7)",
            fontSize: "12px",
            letterSpacing: "0.22em",
          }}
        >
          {s.pageCount}
        </span>
      </div>
      <div className="mt-5">
        <h3
          className="font-serif"
          style={{
            color: "var(--pq-ivory)",
            fontSize: "20px",
            fontWeight: 500,
            letterSpacing: "-0.01em",
            marginBottom: 6,
          }}
        >
          {s.name}
        </h3>
        <p
          className="font-serif italic"
          style={{ color: "rgba(184,149,106,0.85)", fontSize: "12px" }}
        >
          {s.subtitle}
        </p>
      </div>
      <p
        className="mt-4 font-serif"
        style={{
          color: "rgba(245,240,232,0.68)",
          fontSize: "14px",
          lineHeight: 1.6,
        }}
      >
        {s.excerpt}
      </p>
      <div className="mt-auto flex items-center justify-between pt-5">
        <Link
          href={s.href}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          tabIndex={interactiveTabIndex}
          aria-hidden={hidden || undefined}
          className="inline-flex items-center gap-1.5 font-serif italic"
          style={{
            color: "var(--pq-bronze)",
            fontSize: "14px",
            borderBottom: "0.5px solid rgba(184,149,106,0.4)",
            paddingBottom: 2,
          }}
        >
          Open PDF
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onFlip();
          }}
          tabIndex={interactiveTabIndex}
          aria-hidden={hidden || undefined}
          aria-pressed={flipped}
          className="inline-flex items-center gap-1.5 font-serif uppercase"
          style={{
            color: "rgba(184,149,106,0.7)",
            fontSize: "12px",
            letterSpacing: "0.22em",
          }}
        >
          Preview
          <RotateCcw className="h-3 w-3" aria-hidden />
        </button>
      </div>
    </>
  );
}

function BackFaceContent({
  s,
  onFlip,
  hidden,
}: {
  s: FlipSample;
  onFlip: () => void;
  /** True when the back is faded out — keyboard must not land here. */
  hidden: boolean;
}) {
  const interactiveTabIndex = hidden ? -1 : 0;
  return (
    <>
      <div className="relative z-10 flex items-start justify-between">
        <span
          className="font-serif uppercase"
          style={{
            color: "rgba(111,86,54,0.95)",
            fontSize: "12px",
            letterSpacing: "0.22em",
          }}
        >
          {s.preview.kicker}
        </span>
        <span
          className="font-serif italic"
          style={{ color: "rgba(111,86,54,0.7)", fontSize: "12px" }}
        >
          {s.cadence}
        </span>
      </div>
      <h4
        className="relative z-10 mt-4 font-serif italic"
        style={{
          color: "#2A1F13",
          fontSize: "18px",
          fontWeight: 400,
          lineHeight: 1.15,
          letterSpacing: "-0.01em",
        }}
      >
        {s.preview.heading}
      </h4>
      <p
        className="relative z-10 mt-3 font-serif"
        style={{
          color: "rgba(42,31,19,0.78)",
          fontSize: "14px",
          lineHeight: 1.55,
        }}
      >
        {s.preview.lede}
      </p>
      <ul className="relative z-10 mt-3 flex flex-col gap-1.5">
        {s.preview.bullets.map((b) => (
          <li
            key={b}
            className="font-serif"
            style={{
              color: "rgba(42,31,19,0.72)",
              fontSize: "12px",
              lineHeight: 1.5,
              paddingLeft: 10,
              position: "relative",
            }}
          >
            <span
              aria-hidden
              style={{
                position: "absolute",
                left: 0,
                top: 7,
                width: 4,
                height: 1,
                backgroundColor: "rgba(111,86,54,0.7)",
              }}
            />
            {b}
          </li>
        ))}
      </ul>
      <div className="relative z-10 mt-auto flex items-end justify-between pt-4">
        <p
          className="font-serif italic"
          style={{
            color: "rgba(42,31,19,0.6)",
            fontSize: "12px",
            lineHeight: 1.45,
            maxWidth: "20ch",
          }}
        >
          {s.preview.closer}
        </p>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onFlip();
          }}
          tabIndex={interactiveTabIndex}
          aria-hidden={hidden || undefined}
          className="inline-flex items-center gap-1.5 font-serif uppercase"
          style={{
            color: "rgba(111,86,54,0.85)",
            fontSize: "12px",
            letterSpacing: "0.22em",
          }}
        >
          <RotateCcw className="h-3 w-3" aria-hidden />
          Back
        </button>
      </div>
    </>
  );
}
