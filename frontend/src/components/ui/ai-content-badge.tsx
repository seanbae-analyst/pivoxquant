"use client";

/**
 * "AI 판독" mark — AI 기본법 §31 (생성형 AI 사용 사실 고지 · 결과물 표시).
 *
 * Shown on every surface that offers an AI read and on every table whose
 * rows came back from one (lib/ai-read.ts). Guarded by
 * __tests__/ai-label-coverage.test.ts: a file that calls the AI read must
 * import this.
 */
import { useT } from "@/lib/locale";

export function AiContentBadge({ className = "" }: { className?: string }) {
  const t = useT();
  return (
    <span
      className={`inline-flex items-center font-mono uppercase ${className}`}
      style={{
        fontSize: "var(--pq-text-mono-sm)",
        letterSpacing: "0.16em",
        padding: "1px 6px",
        border: "1px solid var(--pq-bronze)",
        borderRadius: 2,
        color: "var(--pq-bronze)",
      }}
      data-testid="ai-content-badge"
    >
      {t("aiRead.badge")}
    </span>
  );
}
