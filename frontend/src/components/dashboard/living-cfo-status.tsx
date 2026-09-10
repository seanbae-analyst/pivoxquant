"use client";

/**
 * <LivingCFOStatusBar /> — sticky hairline bar showing the two layers of
 * the Living CFO product:
 *
 *   Layer 1 · Identity    → InvestmentProfile onboarding (green when set)
 *   Layer 2 · Learning    → Drift + Pulse + Feedback (yellow while training)
 *
 * Layers 3 (Artifacts) and 4 (Companion) were dropped with the surfaces
 * that fed them — the bar no longer reports on things the product does
 * not do.
 *
 * Click opens a modal explaining what the CFO has learned so far and what
 * it's still learning. Clicking a single dot scrolls the modal to the
 * matching layer for a quick "what is this?" read.
 *
 * No data writes. Purely informational. Uses `usePersona` + `usePulse` +
 * `useInvestmentProfile` to compute both readiness signals.
 */

import * as React from "react";
import Link from "next/link";
import { X, Check, Circle } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { PQ_EASE, PQ_DUR_FAST, PQ_DUR_MICRO } from "@/lib/motion";
import { useInvestmentProfile } from "@/lib/hooks";
import {
  usePersona,
  usePulse,
  PERSONA_LABELS,
  declaredSurfaceLabel,
} from "@/lib/cfo/hooks";
import { useFocusTrap } from "@/lib/useFocusTrap";

type Readiness = "ready" | "learning" | "missing";

interface LayerState {
  id: 1 | 2;
  name: string;
  state: Readiness;
  summary: string;
  /** Optional CTA anchor shown inside the modal row. */
  cta?: { label: string; href: string };
}

export function LivingCFOStatusBar() {
  const [open, setOpen] = React.useState(false);
  const [focusedLayer, setFocusedLayer] = React.useState<LayerState["id"] | null>(
    null,
  );

  const { data: profile } = useInvestmentProfile();
  const { data: persona } = usePersona();
  const { data: pulse } = usePulse();

  const layer1State: Readiness = profile?.profile?.profile_type
    ? "ready"
    : "missing";

  // Layer 2: need 3 pulse entries + observed persona + ≥1 feedback record
  // to graduate from "learning" → "ready".
  //
  // 2026-05-20 (Wave 5-B SHIP-BLOCKER fix): `pulse?.history.length` threw
  // "Cannot read properties of undefined (reading 'length')" whenever a
  // legacy/corrupted `pq_cfo_pulse_v1` localStorage snapshot was rehydrated
  // by SWR `fallbackData`. The cache only checks for a truthy object, not
  // for the `history` array, so a `{}` from an older schema was passed
  // through verbatim. This propagated up the React tree, tripped the
  // page-level ErrorBoundary, and blanked /home, /portfolio, /settings (v2)
  // for any user with a stale cache. Array.isArray() guards the access
  // so the cache shape change becomes a no-op instead of a regression.
  const pulseCount = Array.isArray(pulse?.history) ? pulse.history.length : 0;
  const hasObservedPersona = Boolean(persona?.observed?.window_30d);
  const layer2State: Readiness =
    hasObservedPersona && pulseCount >= 3
      ? "ready"
      : hasObservedPersona || pulseCount >= 1
        ? "learning"
        : "missing";


  const layers: LayerState[] = [
    {
      id: 1,
      name: "Identity",
      state: layer1State,
      summary:
        layer1State === "ready"
          ? `Declared persona · ${
              declaredSurfaceLabel(profile?.profile?.profile_type) ?? "set"
            }.`
          : "Five onboarding questions not yet answered.",
      cta:
        layer1State === "ready"
          ? undefined
          : { label: "Take assessment", href: "/onboarding" },
    },
    {
      id: 2,
      name: "Learning",
      state: layer2State,
      summary: `${pulseCount} weekly pulses · ${
        hasObservedPersona ? "30-day drift tracked" : "no drift data yet"
      }.`,
    },
  ];

  /* The outer container handles "click anywhere on the bar to open the
     modal" while each LayerDot is itself a <button> that opens with focus
     on a specific layer. Using a <button> on the outer element nested
     LayerDot buttons inside, which violates HTML — invalid markup +
     hydration errors flooded the console (2026-05-06 live verify).
     Switched to <div role="button"> with keyboard handlers so the same
     a11y semantics survive without the nesting. */
  return (
    <>
      <div
        role="button"
        tabIndex={0}
        onClick={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setOpen(true);
          }
        }}
        className="w-full flex items-center justify-between gap-4 px-4 py-2 hover:bg-[rgba(255,255,255,0.015)] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(184,149,106,0.4)] font-mono"
        style={{
          borderBottom: "0.5px solid rgba(184,149,106,0.22)",
        }}
        aria-label="Living CFO status — click for details"
      >
        <span
          className="uppercase text-pq-caption tracking-[0.26em]"
          style={{ color: "var(--pq-bronze)" }}
        >
          Living CFO
        </span>
        <div className="flex items-center gap-3 sm:gap-5 ml-auto">
          {layers.map((l) => (
            <LayerDot
              key={l.id}
              layer={l}
              onClick={(e) => {
                e.stopPropagation();
                setFocusedLayer(l.id);
                setOpen(true);
              }}
            />
          ))}
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <StatusModal
            onClose={() => {
              setOpen(false);
              setFocusedLayer(null);
            }}
            layers={layers}
            personaLabel={personaBarLabel(persona?.declared?.persona)}
            focusedLayer={focusedLayer}
          />
        )}
      </AnimatePresence>
    </>
  );
}

function LayerDot({
  layer,
  onClick,
}: {
  layer: LayerState;
  onClick: (e: React.MouseEvent) => void;
}) {
  const icon =
    layer.state === "ready" ? (
      <Check className="h-2.5 w-2.5" strokeWidth={3} />
    ) : layer.state === "learning" ? (
      // FINDING-032: §6 forbids spinners on dark surfaces — a shimmer
      // skeleton block carries the "in progress" meaning without the
      // banned animate-spin.
      <span
        className="pq-skeleton-dark inline-block h-2.5 w-2.5"
        style={{ borderRadius: 1 }}
      />
    ) : (
      <Circle className="h-2.5 w-2.5" />
    );

  const color =
    layer.state === "ready"
      ? "var(--pq-live)"
      : layer.state === "learning"
        ? "var(--pq-bronze)"
        : "rgba(245,240,232,0.55)";

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-1.5 text-pq-caption uppercase tracking-[0.22em] px-1 py-0.5 rounded-[2px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(184,149,106,0.4)]"
      style={{ color, background: "transparent" }}
      title={layer.summary}
      aria-label={`Layer ${layer.id} ${layer.name} — ${layer.state}`}
    >
      <span aria-hidden>{icon}</span>
      {/* Verbose label expands at lg: (≥1024), not sm: (≥640). The dashboard
          sidebar appears at md: (≥768) and eats 240px, so between 768–1023 the
          content column is too narrow for four "L# · NAME" chips — the old
          sm: breakpoint let "L4 · COMPANION" overflow the page on iPad. Below
          lg: the compact "L#" form is shown (fits mobile full-width + iPad). */}
      <span className="hidden lg:inline">
        L{layer.id} · {layer.name}
      </span>
      <span className="lg:hidden">L{layer.id}</span>
    </button>
  );
}

function personaBarLabel(id: string | undefined): string | null {
  if (!id) return null;
  return PERSONA_LABELS[id as keyof typeof PERSONA_LABELS] ?? null;
}

function StatusModal({
  onClose,
  layers,
  personaLabel,
  focusedLayer,
}: {
  onClose: () => void;
  layers: LayerState[];
  personaLabel: string | null;
  focusedLayer: LayerState["id"] | null;
}) {
  const focusedRowRef = React.useRef<HTMLLIElement | null>(null);
  const dialogRef = useFocusTrap<HTMLDivElement>(true);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  React.useEffect(() => {
    if (focusedLayer && focusedRowRef.current) {
      focusedRowRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [focusedLayer]);

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: PQ_DUR_MICRO }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Living CFO status"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
    >
      <motion.div
        ref={dialogRef}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        initial={{ y: 8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 8, opacity: 0 }}
        transition={{ duration: PQ_DUR_FAST, ease: PQ_EASE }}
        className="w-full max-w-lg bg-[var(--pq-ink)] border border-[rgba(245,240,232,0.12)] rounded-[2px] p-6"
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <div
              className="text-pq-eyebrow tracking-[0.26em] uppercase"
              style={{ color: "var(--pq-bronze)" }}
            >
              Living CFO · What it knows
            </div>
            <h3 className="mt-1 font-serif text-xl text-[var(--pq-ivory)]">
              {personaLabel ?? "Your personal CFO"}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="-mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center text-[var(--pq-ivory-faint)] hover:text-[var(--pq-ivory)]"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="font-serif text-pq-body-sm text-[var(--pq-ivory-mid)] leading-relaxed">
          It reads the positions you record and the pulses you submit, and
          reflects them back — nothing more.
        </p>

        <ul className="mt-5 space-y-3">
          {layers.map((l) => {
            const focused = focusedLayer === l.id;
            return (
              <li
                key={l.id}
                ref={focused ? focusedRowRef : null}
                className="flex items-start gap-3 p-3 rounded-[2px] border transition-colors"
                style={{
                  borderColor: focused
                    ? "rgba(184,149,106,0.42)"
                    : "var(--pq-ivory-line)",
                  background: focused
                    ? "rgba(184,149,106,0.06)"
                    : "transparent",
                }}
              >
                <span
                  className="mt-[3px] h-2 w-2 rounded-full shrink-0"
                  style={{
                    background:
                      l.state === "ready"
                        ? "var(--pq-live)"
                        : l.state === "learning"
                          ? "var(--pq-bronze)"
                          : "rgba(245,240,232,0.3)",
                  }}
                  aria-hidden
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
                      Layer {l.id} · {l.name}
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-[var(--pq-ivory)]">
                    {l.summary}
                  </div>
                  {l.cta && (
                    <Link
                      href={l.cta.href}
                      onClick={onClose}
                      className="mt-2 inline-flex items-center gap-1 text-pq-caption uppercase tracking-[0.22em]"
                      style={{ color: "var(--pq-bronze)" }}
                    >
                      {l.cta.label}
                      <span aria-hidden>→</span>
                    </Link>
                  )}
                </div>
              </li>
            );
          })}
        </ul>

        <p className="mt-5 text-pq-caption text-[rgba(245,240,232,0.4)]">
          Observational only. Not investment advice.
        </p>
      </motion.div>
    </motion.div>
  );
}

export default LivingCFOStatusBar;
