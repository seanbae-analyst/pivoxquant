/**
 * /mirror-preview — DEV-ONLY visual preview of the 거울 home with sample data.
 *
 * Mirrors the codebase's /reports/preview/* pattern: render a surface with
 * representative sample data so the design can be reviewed without auth or a
 * live backend. Blocked in production (notFound) so it never reaches users.
 *
 * Sample = "성장형 선언 → 최근 30일 균형형 관찰" (영역 이동). The radar vectors
 * are the real growth/balanced centroids from persona_classifier_v2 so the
 * shape gap is faithful. No italic.
 */
import { notFound } from "next/navigation";

import type { MirrorHomeResponse } from "@/lib/types";
import { EditorialHead, FootSignature } from "@/components/ui/editorial";
import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { MirrorHeadline } from "@/components/mirror/mirror-headline";
import { SelfObservedRadar } from "@/components/mirror/self-observed-radar";
import { TwinWeekCard } from "@/components/mirror/twin-week-card";
import { OneThingNudge } from "@/components/mirror/one-thing-nudge";
import { ArchiveLinks } from "@/components/mirror/archive-links";

const SAMPLE: MirrorHomeResponse = {
  ok: true,
  stage: "observed",
  declared: {
    label: "성장형",
    tagline: "성장 가능성에 무게를 두고 관찰합니다.",
    score: 78,
  },
  observed: { label: "균형형", bucket_changed: true, trade_count: 23 },
  gap: [
    { key: "sector_diversity", label: "섹터 분산", direction: "up", delta: 0.4, declared: 0.45, observed: 0.85 },
    { key: "ticker_diversity", label: "종목 다양성", direction: "up", delta: 0.25, declared: 0.55, observed: 0.8 },
    { key: "declared_risk", label: "선언한 위험 감내", direction: "down", delta: -0.25, declared: 0.75, observed: 0.5 },
  ],
  drift: { available: true, descriptor: "영역 이동 관찰" },
  radar: {
    keys: [
      "holding_period", "turnover", "sector_diversity", "ticker_diversity",
      "hold_variance", "loss_cut_discipline", "declared_risk",
      "conviction_stability", "feedback_engagement",
    ],
    labels: [
      "평균 보유기간", "매매 회전율", "섹터 분산", "종목 다양성", "보유기간 편차",
      "손절 규율", "선언한 위험 감내", "확신 안정성", "피드백 반응도",
    ],
    declared: [0.48, 0.3, 0.45, 0.55, 0.45, 0.55, 0.75, 0.65, 0.6],
    observed: [0.55, 0.15, 0.85, 0.8, 0.3, 0.6, 0.5, 0.7, 0.6],
  },
  twin: {
    week_ending: "2026-06-14",
    user_return_pct: 1.1,
    twin_return_pct: 3.3,
    diff_pct: 2.2,
    user_trades_count: 2,
    twin_trades_count: 3,
  },
};

export default function MirrorPreviewPage() {
  if (process.env.NODE_ENV === "production") notFound();
  const data = SAMPLE;

  return (
    <div className="min-h-screen bg-[rgb(5,5,5)] text-[var(--pq-ivory)]">
      <div className="mx-auto max-w-3xl space-y-8 px-5 py-8 md:px-8">
        <div
          className="text-[10.5px] uppercase tracking-[0.2em]"
          style={{ color: "rgba(var(--pq-ivory-rgb), 0.4)" }}
        >
          dev preview · sample data
        </div>

        <EditorialHead>거울</EditorialHead>

        <div className="space-y-8">
          <MirrorHeadline data={data} />

          <section
            className="rounded-[4px] p-4"
            style={{ border: "1px solid var(--pq-ivory-line)" }}
          >
            <div className="flex items-center justify-between">
              <div className="text-[12.5px]" style={{ color: "var(--pq-ivory)" }}>
                선언 vs 관찰
              </div>
              <div
                className="flex items-center gap-3 text-[10.5px]"
                style={{ color: "rgba(var(--pq-ivory-rgb), 0.55)" }}
              >
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: "var(--pq-bronze)" }}
                  />
                  선언(설문)
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: "var(--pq-ivory)" }}
                  />
                  관찰(30일)
                </span>
              </div>
            </div>

            <div className="mt-2 flex justify-center">
              <SelfObservedRadar
                className="w-full max-w-[320px]"
                labels={data.radar.labels}
                declared={data.radar.declared}
                observed={data.radar.observed}
              />
            </div>

            <p
              className="mt-1 text-center text-[10.5px]"
              style={{ color: "var(--pq-bronze)" }}
            >
              점수·등급 없이 — 모양으로만 비춥니다
            </p>
          </section>

          <TwinWeekCard twin={data.twin} />
          <OneThingNudge data={data} />
          <ArchiveLinks />

          <DisclaimerBanner type="behavior-mirror" />
        </div>
      </div>

      <FootSignature />
    </div>
  );
}
