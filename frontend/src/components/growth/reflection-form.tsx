"use client";

/**
 * ReflectionForm — displays today's AI-generated questions and lets
 * the user submit answers + mood score. Posts to /api/growth/reflect.
 */

import { useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import type { GrowthReflection } from "@/lib/types";

const MOOD_OPTIONS = [
  { value: 1, label: "1", emoji: "Terrible" },
  { value: 2, label: "2", emoji: "Bad" },
  { value: 3, label: "3", emoji: "OK" },
  { value: 4, label: "4", emoji: "Good" },
  { value: 5, label: "5", emoji: "Great" },
] as const;

interface ReflectionFormProps {
  reflection: GrowthReflection;
  onSubmitted: () => void;
}

export function ReflectionForm({ reflection, onSubmitted }: ReflectionFormProps) {
  const alreadyAnswered = reflection.answers !== null;
  const [answers, setAnswers] = useState<string[]>(
    reflection.answers ?? reflection.questions.map(() => ""),
  );
  const [mood, setMood] = useState<number>(reflection.mood ?? 3);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnswerChange = useCallback(
    (index: number, value: string) => {
      setAnswers((prev) => {
        const next = [...prev];
        next[index] = value;
        return next;
      });
    },
    [],
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);

      // Validate at least one answer has content
      const hasContent = answers.some((a) => a.trim().length > 0);
      if (!hasContent) {
        setError("하나 이상의 질문에 답변해주세요.");
        return;
      }

      setSubmitting(true);
      try {
        await apiFetch(API.growth.reflect, {
          method: "POST",
          body: JSON.stringify({
            reflection_id: reflection.id,
            answers,
            mood,
          }),
        });
        onSubmitted();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "제출에 실패했습니다.",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [answers, mood, reflection.id, onSubmitted],
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {reflection.questions.map((question, i) => {
        const fieldId = `reflection-q-${i}`;
        return (
          <div key={i} className="space-y-2">
            <label
              htmlFor={fieldId}
              className="block font-mono text-pq-mono-sm uppercase tracking-[0.22em] text-[var(--pq-bronze)]"
            >
              Q{i + 1}. <span className="font-serif normal-case tracking-normal text-[rgba(245,240,232,0.82)]">{question}</span>
            </label>
            <textarea
              id={fieldId}
              value={answers[i] ?? ""}
              onChange={(e) => handleAnswerChange(i, e.target.value)}
              disabled={alreadyAnswered}
              rows={2}
              placeholder="답변을 입력하세요..."
              className="w-full resize-none rounded-sm border border-[var(--pq-ivory-line)] bg-[rgba(255,255,255,0.02)] px-3 py-2 text-sm text-[var(--pq-ivory)] placeholder:text-[rgba(245,240,232,0.35)] focus:border-[var(--pq-bronze)] focus:outline-none focus:ring-1 focus:ring-[var(--pq-bronze)] disabled:cursor-not-allowed disabled:bg-[rgba(255,255,255,0.01)] disabled:text-[rgba(245,240,232,0.45)]"
            />
          </div>
        );
      })}

      {/* Mood selector */}
      <div className="space-y-2">
        <label className="block font-mono text-pq-mono-sm uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
          오늘 기분 (1-5)
        </label>
        <div className="flex gap-2">
          {MOOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setMood(opt.value)}
              disabled={alreadyAnswered}
              className={`flex h-10 w-10 items-center justify-center rounded-full border font-mono text-sm font-medium tabular-nums transition-colors ${
                mood === opt.value
                  ? "border-[var(--pq-bronze)] bg-[rgba(184,149,106,0.18)] text-[var(--pq-bronze)]"
                  : "border-[var(--pq-ivory-line)] text-[rgba(245,240,232,0.55)] hover:border-[var(--pq-bronze-light)] hover:text-[var(--pq-bronze-light)]"
              } disabled:cursor-not-allowed disabled:opacity-50`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-[rgba(245,240,232,0.45)]">
          {MOOD_OPTIONS.find((o) => o.value === mood)?.emoji}
        </p>
      </div>

      {error && (
        <p className="text-sm text-[#d97a7a]">{error}</p>
      )}

      {!alreadyAnswered && (
        <button
          type="submit"
          disabled={submitting}
          className="pq-ink-btn-bronze disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "제출 중..." : "회고 제출"}
        </button>
      )}

      {alreadyAnswered && (
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-[var(--pq-bronze)]">
          오늘의 회고가 이미 제출되었습니다.
        </p>
      )}
    </form>
  );
}
