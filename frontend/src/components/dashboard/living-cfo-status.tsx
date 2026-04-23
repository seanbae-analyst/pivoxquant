"use client";

/**
 * <LivingCFOStatusBar /> — sticky hairline bar showing the three layers of
 * the Living CFO product:
 *
 *   Layer 1 · Identity    → InvestmentProfile onboarding (green when set)
 *   Layer 2 · Learning    → Drift + Pulse + Feedback (yellow while training)
 *   Layer 3 · Artifacts   → Delivered PDFs / emails
 *
 * Click opens a modal explaining what the CFO has learned so far and what
 * it's still learning.
 *
 * No data writes. Purely informational. Uses `usePersona` + `usePulse` +
 * existing `useInvestmentProfile` + `useArtifacts` to compute the three
 * readiness signals. Gracefully degrades when any of those endpoints 404.
 */

import * as React from "react";
import { X, Check, Circle, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useInvestmentProfile, useArtifacts } from "@/lib/hooks";
import { usePersona, usePulse, PERSONA_LABELS } from "@/lib/cfo/hooks";

type Readiness = "ready" | "learning" | "missing";

interface LayerState {
  id: 1 | 2 | 3;
  name: string;
  state: Readiness;
  summary: string;
}

export function LivingCFOStatusBar() {
  const [open, setOpen] = React.useState(false);

  const { data: profile } = useInvestmentProfile();
  const { data: persona } = usePersona();
  const { data: pulse } = usePulse();
  const { artifacts } = useArtifacts({ type: "all", since: "all" });

  const layer1State: Readiness = profile?.profile?.profile_type
    ? "ready"
    : "missing";

  // Layer 2: need 3 pulse entries + observed persona + ≥1 feedback record
  // to graduate from "learning" → "ready".
  const pulseCount = pulse?.history.length ?? 0;
  const hasObservedPersona = Boolean(persona?.observed?.window_30d);
  const layer2State: Readiness =
    hasObservedPersona && pulseCount >= 3
      ? "ready"
      : hasObservedPersona || pulseCount >= 1
        ? "learning"
        : "missing";

  const layer3State: Readiness =
    artifacts.length >= 3 ? "ready" : artifacts.length >= 1 ? "learning" : "missing";

  const layers: LayerState[] = [
    {
      id: 1,
      name: "Identity",
      state: layer1State,
      summary:
        layer1State === "ready"
          ? `Declared persona · ${profile?.profile?.profile_type ?? "set"}.`
          : "20-question assessment not yet taken.",
    },
    {
      id: 2,
      name: "Learning",
      state: layer2State,
      summary: `${pulseCount} weekly pulses · ${
        hasObservedPersona ? "30-day drift tracked" : "no drift data yet"
      }.`,
    },
    {
      id: 3,
      name: "Artifacts",
      state: layer3State,
      summary: `${artifacts.length} delivered to your inbox.`,
    },
  ];

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full flex items-center justify-between gap-4 px-4 py-2 hover:bg-[rgba(255,255,255,0.015)] transition-colors"
        style={{
          borderBottom: "0.5px solid rgba(184,149,106,0.22)",
          fontFamily: "var(--font-mono), ui-monospace",
        }}
        aria-label="Living CFO status — click for details"
      >
        <span
          className="uppercase text-[9.5px] tracking-[0.26em]"
          style={{ color: "var(--pq-bronze)" }}
        >
          Living CFO
        </span>
        <div className="flex items-center gap-5 ml-auto">
          {layers.map((l) => (
            <LayerDot key={l.id} layer={l} />
          ))}
        </div>
      </button>

      <AnimatePresence>
        {open && <StatusModal onClose={() => setOpen(false)} layers={layers} personaLabel={personaBarLabel(persona?.declared?.persona)} />}
      </AnimatePresence>
    </>
  );
}

function LayerDot({ layer }: { layer: LayerState }) {
  const icon =
    layer.state === "ready" ? (
      <Check className="h-2.5 w-2.5" strokeWidth={3} />
    ) : layer.state === "learning" ? (
      <Loader2 className="h-2.5 w-2.5 animate-spin" />
    ) : (
      <Circle className="h-2.5 w-2.5" />
    );

  const color =
    layer.state === "ready"
      ? "#7db487"
      : layer.state === "learning"
        ? "var(--pq-bronze)"
        : "rgba(245,240,232,0.35)";

  return (
    <span
      className="flex items-center gap-1.5 text-[9.5px] uppercase tracking-[0.22em]"
      style={{ color }}
      title={layer.summary}
    >
      <span aria-hidden>{icon}</span>
      <span className="hidden sm:inline">
        L{layer.id} · {layer.name}
      </span>
      <span className="sm:hidden">L{layer.id}</span>
    </span>
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
}: {
  onClose: () => void;
  layers: LayerState[];
  personaLabel: string | null;
}) {
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Living CFO status"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
    >
      <motion.div
        onClick={(e) => e.stopPropagation()}
        initial={{ y: 8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 8, opacity: 0 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-lg bg-[var(--pq-ink)] border border-[rgba(245,240,232,0.12)] rounded-[2px] p-6"
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <div
              className="text-[10px] tracking-[0.26em] uppercase"
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
            className="text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-ivory)]"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="font-serif text-[13px] text-[rgba(245,240,232,0.65)] leading-relaxed">
          Two years in, this dashboard knows your style better than you do.
          It learns from every position you hold and every pulse you submit.
        </p>

        <ul className="mt-5 space-y-3">
          {layers.map((l) => (
            <li
              key={l.id}
              className="flex items-start gap-3 p-3 rounded-[2px] border border-[rgba(245,240,232,0.08)]"
            >
              <span
                className="mt-[3px] h-2 w-2 rounded-full shrink-0"
                style={{
                  background:
                    l.state === "ready"
                      ? "#7db487"
                      : l.state === "learning"
                        ? "var(--pq-bronze)"
                        : "rgba(245,240,232,0.3)",
                }}
                aria-hidden
              />
              <div>
                <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
                  Layer {l.id} · {l.name}
                </div>
                <div className="mt-1 text-sm text-[var(--pq-ivory)]">
                  {l.summary}
                </div>
              </div>
            </li>
          ))}
        </ul>

        <p className="mt-5 text-[10.5px] text-[rgba(245,240,232,0.4)]">
          Observational only. Not investment advice.
        </p>
      </motion.div>
    </motion.div>
  );
}

export default LivingCFOStatusBar;
