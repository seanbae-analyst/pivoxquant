"use client";

/**
 * <LivingCFOStatusBar /> — sticky hairline bar showing the two layers the
 * CFO reads about you.
 *
 * 2026-09-19: the visible strings said "Living CFO" — a feature name that
 * was deleted (it is gone from the landing nav, top-nav.tsx:22) and that
 * the dashboard was the last surface still carrying it. The CEO-approved
 * umbrella "당신 포트폴리오의 CFO" is untouched; only the dead feature name
 * is. The file name is kept so the importing pages and the rollback path
 * stay stable.
 *
 * 2026-10-07: the bar and modal went Korean (CEO "영문 라벨도 한글로") —
 * the English mono-eyebrow house rule (commit a09376e0) no longer holds here.
 * Layer names follow /mirror's vocabulary: 선언 (onboarding answers) and
 * 관찰 (what the record shows).
 *
 * 2026-09-29: mounted on /portfolio and /settings only. /mirror dropped it —
 * the page IS the declared-vs-observed reading the modal summarised. The
 * modal now links to /mirror for that reading instead of restating it.
 *
 *   Layer 1 · 선언 (was Identity) → InvestmentProfile onboarding (green when set)
 *   Layer 2 · 관찰 (was Learning) → Drift + Pulse + Feedback (yellow while training)
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
} from "@/lib/cfo/hooks";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { useT } from "@/lib/locale";

type Readiness = "ready" | "learning" | "missing";

/** Spoken state for each layer's accessible name. */
const READINESS_LABEL: Record<Readiness, string> = {
  ready: "갖춰짐",
  learning: "쌓는 중",
  missing: "아직 없음",
};

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
  const t = useT();

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
      name: "선언",
      state: layer1State,
      // 2026-09-29: used to read "Declared persona · 성장형." — no type
      // labels (CLAUDE.md "유형 라벨·점수는 만들지 않는다"). The fact is that
      // the answers exist; what they say is on /mirror.
      summary:
        layer1State === "ready"
          ? "온보딩 다섯 문항에 답했습니다."
          : "온보딩 다섯 문항에 아직 답하지 않았습니다.",
      cta:
        layer1State === "ready"
          ? undefined
          : { label: "다섯 문항 답하기", href: "/onboarding" },
    },
    {
      id: 2,
      name: "관찰",
      state: layer2State,
      // 2026-09-29: "30-day drift tracked" is gone. It showed whenever
      // `observed.window_30d` existed — and the backend always sends that
      // window (an empty one too), so it claimed tracking that was not
      // happening. Only the count that is actually measured stays.
      summary: t("dashboard.cfoStatus.pulsesRecorded", {
        n: String(pulseCount),
      }),
      // The declared-vs-observed reading itself lives on /mirror; this bar
      // only reports that it exists and points there (2026-09-29).
      cta: hasObservedPersona
        ? { label: "거울에서 선언과 관찰 비교하기", href: "/mirror" }
        : undefined,
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
        aria-label="CFO 현황 — 눌러서 자세히 보기"
      >
        <span
          className="text-pq-caption"
          style={{ color: "var(--pq-bronze)" }}
        >
          CFO · 현황
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
      className="flex items-center gap-1.5 text-pq-caption px-1 py-0.5 rounded-[2px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(184,149,106,0.4)]"
      style={{ color, background: "transparent" }}
      title={layer.summary}
      aria-label={`${layer.id}단계 ${layer.name} — ${READINESS_LABEL[layer.state]}`}
    >
      <span aria-hidden>{icon}</span>
      {/* 2026-10-07: the Korean names (선언 / 관찰) are two syllables — shorter
          than the old compact "L1" / "L2" form — so one label fits every width.
          (Before, "L# · NAME" only expanded at lg: so English names like
          "L4 · COMPANION" could not overflow the iPad column.) */}
      <span>{layer.name}</span>
    </button>
  );
}

function StatusModal({
  onClose,
  layers,
  focusedLayer,
}: {
  onClose: () => void;
  layers: LayerState[];
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
      aria-label="CFO 현황"
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
              className="text-pq-eyebrow"
              style={{ color: "var(--pq-bronze)" }}
            >
              CFO · 지금까지 읽은 것
            </div>
            <h3 className="mt-1 font-serif text-xl text-[var(--pq-ivory)]">
              당신의 CFO
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="-mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center text-[var(--pq-ivory-faint)] hover:text-[var(--pq-ivory)]"
            aria-label="닫기"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="font-serif text-pq-body-sm text-[var(--pq-ivory-mid)] leading-relaxed">
          기록한 보유 종목과 주간 펄스를 읽고, 그대로 되비춥니다. 그 이상은
          하지 않습니다.
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
                    <span className="text-pq-eyebrow text-[var(--pq-bronze)]">
                      {l.id}단계 · {l.name}
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-[var(--pq-ivory)]">
                    {l.summary}
                  </div>
                  {l.cta && (
                    <Link
                      href={l.cta.href}
                      onClick={onClose}
                      className="mt-2 inline-flex items-center gap-1 text-pq-caption"
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
          관찰한 내용일 뿐이며, 투자자문이 아닙니다.
        </p>
      </motion.div>
    </motion.div>
  );
}

export default LivingCFOStatusBar;
