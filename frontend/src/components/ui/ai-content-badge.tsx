"use client";

/**
 * <AiContentBadge /> — AI-generated content disclosure badge.
 *
 * Regulatory ③ (2026-01 시행 의무):
 *   AI 기본법 / 정보통신망법 — 이용자에게 AI 가 생성한 콘텐츠임을
 *   명확히 표시할 의무. 본 컴포넌트는 모든 AI 산출물 surface 상단(또는
 *   콘텐츠 인접) 에 배치하여 한국어 + 영문 병기 라벨을 제공한다.
 *
 * 본 배지는 자본시장법 면책 (DisclaimerBanner) 과는 별개의 규제 대응이며,
 * 두 컴포넌트는 같은 화면에 공존 가능 (서로 다른 법령 대응).
 *
 * Design system v3:
 *   - bronze 11px 모노 라벨 (var(--pq-bronze))
 *   - 11px primary KO + 10px subline EN
 *   - 선/배경 없음 (인라인 라벨 형태). 카드 안에서는 hairline 보더 옵션.
 */

import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export const AI_CONTENT_LABEL_KO = "AI 생성 콘텐츠 (참고용)";
export const AI_CONTENT_LABEL_EN = "AI-generated content (informational)";

interface AiContentBadgeProps {
  /** 인라인(텍스트만) vs framed(보더+배경) 표시 변형. */
  variant?: "inline" | "framed";
  /** 추가 className. */
  className?: string;
}

export function AiContentBadge({
  variant = "inline",
  className,
}: AiContentBadgeProps) {
  const isFramed = variant === "framed";

  return (
    <div
      role="note"
      aria-label="AI-generated content disclosure"
      data-ai-content-label="true"
      className={cn(
        "inline-flex items-start gap-1.5",
        isFramed &&
          "rounded-[2px] border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] px-2.5 py-1.5",
        className,
      )}
    >
      <Sparkles
        className="h-3 w-3 shrink-0 mt-[2px]"
        style={{ color: "var(--pq-bronze)" }}
        aria-hidden="true"
      />
      <span className="flex flex-col leading-tight">
        <span
          className="font-mono text-[11px] uppercase"
          style={{
            letterSpacing: "0.18em",
            color: "var(--pq-bronze)",
          }}
        >
          {AI_CONTENT_LABEL_KO}
        </span>
        <span
          className="font-mono text-[10px] uppercase opacity-70"
          style={{
            letterSpacing: "0.16em",
            color: "var(--pq-bronze-light, var(--pq-bronze))",
          }}
        >
          {AI_CONTENT_LABEL_EN}
        </span>
      </span>
    </div>
  );
}

export default AiContentBadge;
