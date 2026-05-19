"use client";

/**
 * ThreeLayers — Living CFO 3-Layer stack visualization.
 * -----------------------------------------------------------------------
 * Layer 3: Artifact    (15 reports × 8 personas — PDF/email/voice)
 * Layer 2: Learning    (Drift · Pulse · Feedback — rolling window)
 * Layer 1: Identity    (InvestmentProfile — onboarding 20Q)
 *
 * CSS 3D isometric stack (no Three.js). Pure motion/react for enter anim.
 * Mobile: stacks vertically at 375px; desktop: 3D skew.
 * Colors: Vantablack + Bronze + Ivory. Palette-safe.
 */

import { useRef } from "react";
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
  type MotionValue,
} from "motion/react";
import { Layers, Activity, Fingerprint } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion";

type LayerDef = {
  n: number;
  label: string;
  title: string;
  korean: string;
  blurb: string;
  icon: typeof Layers;
  offset: number;
};

const LAYERS: readonly LayerDef[] = [
  {
    n: 3,
    label: "Layer 3",
    title: "Artifact",
    korean: "산출물",
    blurb:
      "15 research reports × 8 personas. Delivered as PDF, email, or voice brief.",
    icon: Layers,
    offset: 0,
  },
  {
    n: 2,
    label: "Layer 2",
    title: "Learning",
    korean: "학습",
    blurb:
      "Drift detection, weekly pulse, feedback loops. Five continuous signals.",
    icon: Activity,
    offset: 34,
  },
  {
    n: 1,
    label: "Layer 1",
    title: "Identity",
    korean: "정체성",
    blurb: "InvestmentProfile — a 20-question onboarding that anchors it all.",
    icon: Fingerprint,
    offset: 68,
  },
] as const;

/* ────────────────────────────────────────────────────────────
   IsoLayer — single rectangle in the 3D stack. Animates its
   opacity + translateZ based on the parent section's scroll
   progress so the three layers emerge one-by-one as the user
   scrolls (worldquantfoundry-style chapter pause).
   ──────────────────────────────────────────────────────────── */
function IsoLayer({
  layer,
  idx,
  total,
  progress,
  reduce,
}: {
  layer: LayerDef;
  idx: number;
  total: number;
  progress: MotionValue<number>;
  reduce: boolean;
}) {
  // Scroll windows: layer 0 (top) is fully visible by 0.30,
  // layer 1 by 0.50, layer 2 by 0.70. Section is tall (sticky-pin
  // window), so these windows leave breathing room.
  const start = 0.12 + idx * 0.18;
  const end = start + 0.18;

  const opacity = useTransform(progress, [start, end], [0.05, 1]);
  // Lift each layer up in Z as it reveals (parallax).
  const baseZ = (total - 1 - idx) * 44;
  const z = useTransform(progress, [start, end], [baseZ - 32, baseZ]);

  const bg =
    idx === 0
      ? "rgba(245, 240, 232, 0.92)"
      : idx === 1
        ? "rgba(184, 149, 106, 0.85)"
        : "rgba(10, 10, 10, 0.95)";

  return (
    <motion.div
      className="absolute left-1/2 top-1/2 rounded-sm"
      style={{
        width: "68%",
        height: "68%",
        opacity: reduce ? 1 : opacity,
        translateX: "-50%",
        translateY: "-50%",
        translateZ: reduce ? baseZ : z,
        backgroundColor: bg,
        boxShadow:
          "0 12px 40px -12px rgba(0,0,0,0.55), 0 0 0 0.5px rgba(139,111,71,0.4)",
        color: idx === 2 ? "var(--pq-ivory)" : "var(--pq-ink)",
      }}
    >
      {/* Label corner */}
      <div
        className="absolute left-3 top-3 flex items-center gap-1.5 font-mono"
      >
        <span
          className="text-pq-kicker uppercase tracking-widest font-mono"
          style={{
            color:
              idx === 2 ? "rgba(184,149,106,0.85)" : "rgba(10,10,10,0.55)",
            letterSpacing: "0.2em",
          }}
        >
          L{layer.n}
        </span>
      </div>

      {/* Faux doc lines */}
      <div className="absolute inset-x-5 top-10 space-y-1.5">
        {Array.from({ length: 5 }).map((_, li) => (
          <div
            key={li}
            className="h-[2px] rounded-full"
            style={{
              width: `${70 - li * 8}%`,
              backgroundColor:
                idx === 2 ? "rgba(245,240,232,0.25)" : "rgba(10,10,10,0.18)",
            }}
          />
        ))}
      </div>
    </motion.div>
  );
}

export function ThreeLayers() {
  const reduce = useReducedMotion();
  const sectionRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end end"],
  });

  return (
    <section
      ref={sectionRef}
      id="pq-three-layers"
      className="relative py-24 md:py-36"
      style={{ backgroundColor: "#050505", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        {/* Eyebrow */}
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-10 inline-flex items-center gap-2.5"
        >
          <span
            aria-hidden
            className="h-px w-7"
            style={{ backgroundColor: "rgba(139, 111, 71, 0.7)" }}
          />
          <span
            className="font-serif text-pq-mono-sm uppercase"
            style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
          >
            The Architecture · 3-Layer Stack
          </span>
        </motion.div>

        <motion.h2
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="pq-silver-matte font-serif mb-6 md:mb-8"
          style={{
            fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
            lineHeight: 1.08,
            letterSpacing: "-0.02em",
            fontWeight: 500,
          }}
        >
          Three layers.
          <br />
          One learning CFO.
        </motion.h2>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="font-serif mb-16 md:mb-24 max-w-xl"
          style={{
            fontSize: "clamp(15px, 1.3vw, 17px)",
            lineHeight: 1.65,
            color: "rgba(245, 240, 232, 0.65)",
          }}
        >
          매일 쓰는 Artifact는 Learning에서 나오고, Learning은 당신의
          Identity 위에 서 있다. 2년 뒤, 층이 두꺼워진다.
        </motion.p>

        <div className="grid grid-cols-1 gap-12 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] md:gap-16 lg:gap-24 items-center">
          {/* LEFT: Isometric stack visual — sticky-pinned on desktop so it
              "holds" while the right-side layer cards reveal one-by-one. */}
          <div className="md:sticky md:top-[18vh] self-start">
            <div
              className="relative mx-auto w-full max-w-[460px] aspect-[1/1.1]"
              style={{ perspective: "1200px" }}
            >
              <div
                className="relative h-full w-full"
                style={{
                  transformStyle: "preserve-3d",
                  transform:
                    "rotateX(56deg) rotateZ(-42deg) translateY(-18px)",
                }}
              >
                {LAYERS.map((layer, idx) => (
                  <IsoLayer
                    key={layer.n}
                    layer={layer}
                    idx={idx}
                    total={LAYERS.length}
                    progress={scrollYProgress}
                    reduce={!!reduce}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* RIGHT: Layer labels */}
          <motion.ol
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-80px" }}
            variants={stagger}
            className="space-y-8"
          >
            {LAYERS.map((layer) => {
              const Icon = layer.icon;
              return (
                <motion.li
                  key={layer.n}
                  variants={fadeUp}
                  className="border-t pt-6 grid grid-cols-[auto_minmax(0,1fr)] gap-5"
                  style={{ borderColor: "var(--pq-border)" }}
                >
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-sm"
                    style={{
                      border: "0.5px solid rgba(139,111,71,0.45)",
                      color: "var(--pq-bronze)",
                    }}
                    aria-hidden
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="flex items-baseline gap-3 mb-2">
                      <span
                        className="font-mono text-pq-eyebrow uppercase tabular-nums"
                        style={{
                          letterSpacing: "0.22em",
                          color: "var(--pq-bronze)",
                        }}
                      >
                        {layer.label}
                      </span>
                      <span
                        className="font-serif text-pq-mono-sm italic"
                        style={{ color: "rgba(245,240,232,0.45)" }}
                      >
                        {layer.korean}
                      </span>
                    </div>
                    <h3
                      className="font-serif mb-2"
                      style={{
                        fontSize: "clamp(20px, 1.8vw, 26px)",
                        lineHeight: 1.12,
                        color: "var(--pq-ivory)",
                        fontWeight: 500,
                      }}
                    >
                      {layer.title}
                    </h3>
                    <p
                      className="font-serif"
                      style={{
                        fontSize: "var(--pq-text-lead)",
                        lineHeight: 1.6,
                        color: "rgba(245,240,232,0.65)",
                      }}
                    >
                      {layer.blurb}
                    </p>
                  </div>
                </motion.li>
              );
            })}
          </motion.ol>
        </div>
      </div>
    </section>
  );
}

export default ThreeLayers;
