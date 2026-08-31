"use client";

/**
 * <LivingMirrorCta />
 *
 * /profile v2 — persona-deep capstone CTA. Lets the user generate and download
 * their own "Living Mirror" PDF: the declared-persona radar, the observed
 * behaviour overlay, and the drift trajectory on one editorial page.
 *
 * Flow:
 *   1. POST /api/artifacts/living-mirror/generate → { ok, id, data }.
 *      (Backend opens to all tiers via LAUNCH_FREE_ALL_TIERS — no TierGate.)
 *   2. Once an id exists, "PDF 다운로드" fetches
 *      /api/artifacts/living-mirror/download/<id> with credentials.
 *
 * 4 legal conditions wired here (legal-kr-fintech):
 *   · AI label — the PDF cover + footer carry the visible "AI가 생성한 관찰
 *     기록입니다" label (backend template). This CTA additionally states it in
 *     the card copy before generation so the expectation is set up-front.
 *   · CTA microcopy — the line under the generate button: "투자성향 진단이나
 *     투자 조언이 아닙니다" (negation only — §101 expectation correction).
 *   · License — surfaced in the PDF footer ("등록번호: 미신고 …"), not here.
 *   · 410 graceful — download intercepts 404/410 and shows a "다시 생성" prompt
 *     instead of navigating to a raw JSON error page (Railway ephemeral disk).
 *
 * 🔴 Copy guardrails: no 추천/조언/진단/매수/매도/BUY/SELL/보장/수익 except in
 * the legally-required NEGATION ("…이 아닙니다"). No score / grade / rank /
 * "상위 N%". No fake data — the card reflects only what the backend returns.
 */

import * as React from "react";
import { toast } from "sonner";

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { ApiError } from "@/lib/api";
import type { LivingMirrorGenerateResponse } from "@/lib/types";

type Phase = "idle" | "generating" | "ready" | "error";

/** Stage → factual one-liner describing what the PDF will contain. Observation
 *  vocabulary only — no judgement, score, or advice. */
const STAGE_NOTE: Record<string, string> = {
  new: "선언한 성향의 형태를 레이더로 비춥니다. 체결이 쌓이면 관찰된 행동이 겹쳐집니다.",
  observed: "선언한 형태와 관찰된 행동을 같은 축 위에 겹쳐, 가장 크게 갈라지는 축을 사실로 표시합니다.",
  trajectory:
    "선언·관찰 형태에 더해, 시간에 따라 형태가 어떻게 움직였는지 궤적으로 비춥니다.",
};

export function LivingMirrorCta() {
  const [phase, setPhase] = React.useState<Phase>("idle");
  const [artifactId, setArtifactId] = React.useState<number | null>(null);
  const [stage, setStage] = React.useState<string | null>(null);
  const [downloading, setDownloading] = React.useState(false);

  const handleGenerate = React.useCallback(async () => {
    setPhase("generating");
    try {
      const res = await apiFetch<LivingMirrorGenerateResponse>(
        API.artifacts.livingMirrorGenerate,
        { method: "POST", body: JSON.stringify({}), timeoutMs: 60_000 },
      );
      if (!res?.ok || typeof res.id !== "number") {
        throw new Error("Unexpected response");
      }
      setArtifactId(res.id);
      setStage(res.data?.stage ?? null);
      setPhase("ready");
      toast.success("페르소나 거울이 준비됐습니다", {
        description: "아래에서 PDF로 내려받을 수 있습니다.",
      });
    } catch (err) {
      setPhase("error");
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "생성에 실패했습니다.";
      toast.error("거울 생성에 실패했습니다", { description: msg });
    }
  }, []);

  // 410-graceful download: intercept 404/410 (Railway ephemeral disk lost the
  // rendered PDF) and prompt a re-generate instead of leaking raw JSON.
  const handleDownload = React.useCallback(async () => {
    if (artifactId === null) return;
    setDownloading(true);
    try {
      const resp = await fetch(API.artifacts.livingMirrorDownload(artifactId), {
        credentials: "include",
      });
      if (!resp.ok) {
        if (resp.status === 410 || resp.status === 404) {
          // Force the user back to the generate step — the persisted row's PDF
          // is gone, so the existing id can't be downloaded again.
          setPhase("idle");
          setArtifactId(null);
          toast.error("PDF가 아직 준비되지 않았습니다", {
            description: "다시 생성해 주세요. 파일이 서버에서 만료됐을 수 있습니다.",
            duration: 7000,
          });
          return;
        }
        toast.error(`PDF 다운로드 실패 (${resp.status})`, {
          description: "잠시 후 다시 시도해 주세요.",
        });
        return;
      }
      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `living-mirror-${artifactId}.pdf`;
      a.click();
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      toast.error("PDF 다운로드 중 오류가 발생했습니다", {
        description:
          err instanceof Error ? err.message : "네트워크 상태를 확인해 주세요.",
      });
    } finally {
      setDownloading(false);
    }
  }, [artifactId]);

  const stageNote = stage ? STAGE_NOTE[stage] : null;

  // DORMANT since e064118e. `POST /api/artifacts/living-mirror/generate` went
  // with the artefact tree, so the button below would 404 on every click.
  //
  // Everything else in this file is deliberately kept: the generate call, the
  // 410-graceful download, the legal copy and its four wired conditions. When
  // the mirror-based generator lands, flipping this one constant restores the
  // whole flow — no rewrite. Until then the card states plainly that it is not
  // ready, because offering an action that cannot complete is the failure mode
  // this branch has been removing everywhere else.
  const GENERATE_AVAILABLE = false;

  if (!GENERATE_AVAILABLE) {
    return (
      <section
        aria-labelledby="living-mirror-heading"
        style={{
          background: "rgba(255,255,255,0.02)",
          border: "1px solid var(--pq-ivory-line)",
          borderRadius: 4,
          padding: 32,
          marginBottom: 48,
        }}
      >
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
            marginBottom: 8,
          }}
        >
          Living Mirror · 페르소나 캡스톤
        </div>
        <h2
          id="living-mirror-heading"
          className="font-display"
          style={{
            fontWeight: 500,
            fontSize: "clamp(24px, 3vw, 32px)",
            lineHeight: 1.15,
            color: "var(--pq-ivory, #F5F0E8)",
            margin: "0 0 12px",
          }}
        >
          내 페르소나 거울 PDF
        </h2>
        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.6,
            color: "rgba(245,240,232,0.72)",
            maxWidth: 620,
            margin: 0,
          }}
        >
          지금은 만들 수 없습니다. 거울 기록을 바탕으로 다시 만드는 중입니다.
        </p>
      </section>
    );
  }

  return (
    <section
      aria-labelledby="living-mirror-heading"
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid var(--pq-ivory-line)",
        borderRadius: 4,
        padding: 32,
        marginBottom: 48,
        position: "relative",
      }}
    >
      <div
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 8,
        }}
      >
        Living Mirror · 페르소나 캡스톤
      </div>

      <h2
        id="living-mirror-heading"
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(24px, 3vw, 32px)",
          lineHeight: 1.15,
          color: "var(--pq-ivory, #F5F0E8)",
          margin: "0 0 12px",
        }}
      >
        내 페르소나 거울 PDF
      </h2>

      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.6,
          color: "rgba(245,240,232,0.72)",
          maxWidth: 620,
          margin: "0 0 18px",
        }}
      >
        설문에서 <strong>선언한 성향</strong>과 실제 체결에서{" "}
        <strong>관찰된 행동</strong>의 형태를 같은 축 위에 비추고, 시간에 따른
        변화를 궤적으로 정리한 한 장의 기록입니다. 점수도 등급도 매기지 않으며,
        해석은 온전히 당신의 몫입니다.
      </p>

      {/* AI label — visible expectation-setting before generation
          (조건 1, 커버·footer 라벨과 별개로 CTA 카드에도 노출). */}
      <div
        role="note"
        aria-label="AI 생성물 고지"
        className="font-mono uppercase"
        style={{
          display: "inline-block",
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.14em",
          color: "var(--pq-bronze)",
          border: "1px solid var(--pq-bronze-15, rgba(184,149,106,0.3))",
          borderRadius: 2,
          padding: "5px 10px",
          marginBottom: 20,
        }}
      >
        AI가 생성한 관찰 기록입니다
      </div>

      {/* Post-generate stage note (factual, only when backend returned one) */}
      {phase === "ready" && stageNote && (
        <p
          aria-live="polite"
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.55,
            color: "rgba(245,240,232,0.62)",
            maxWidth: 620,
            margin: "0 0 18px",
          }}
        >
          {stageNote}
        </p>
      )}

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 16,
        }}
      >
        <button
          type="button"
          onClick={handleGenerate}
          disabled={phase === "generating"}
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            color: "var(--pq-bronze, #B8956A)",
            background: "transparent",
            border: "none",
            borderBottom: "1px solid var(--pq-bronze-15, rgba(184,149,106,0.15))",
            paddingBottom: 2,
            cursor: phase === "generating" ? "wait" : "pointer",
          }}
        >
          {phase === "generating"
            ? "생성 중…"
            : phase === "ready"
              ? "다시 생성 ›"
              : "내 거울 생성 ›"}
        </button>

        {phase === "ready" && artifactId !== null && (
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.18em",
              color: "var(--pq-ivory, #F5F0E8)",
              background: "transparent",
              border: "none",
              borderBottom: "1px solid rgba(245,240,232,0.25)",
              paddingBottom: 2,
              cursor: downloading ? "wait" : "pointer",
            }}
          >
            {downloading ? "내려받는 중…" : "PDF 다운로드 ↓"}
          </button>
        )}
      </div>

      {/* CTA microcopy — negation only (조건 2). Sets the expectation before
          the button press so the artifact is never read as advice. */}
      <p
        className="font-mono"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.04em",
          color: "rgba(245,240,232,0.45)",
          margin: "14px 0 0",
        }}
      >
        투자성향 진단이나 투자 조언이 아닙니다.
      </p>
    </section>
  );
}

export default LivingMirrorCta;
