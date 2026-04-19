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
      {reflection.questions.map((question, i) => (
        <div key={i} className="space-y-2">
          <label className="block text-sm font-medium text-slate-700">
            Q{i + 1}. {question}
          </label>
          <textarea
            value={answers[i] ?? ""}
            onChange={(e) => handleAnswerChange(i, e.target.value)}
            disabled={alreadyAnswered}
            rows={2}
            placeholder="답변을 입력하세요..."
            className="w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
          />
        </div>
      ))}

      {/* Mood selector */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">
          오늘 기분 (1-5)
        </label>
        <div className="flex gap-2">
          {MOOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setMood(opt.value)}
              disabled={alreadyAnswered}
              className={`flex h-10 w-10 items-center justify-center rounded-full border text-sm font-medium transition-colors ${
                mood === opt.value
                  ? "border-green-500 bg-green-50 text-green-700"
                  : "border-slate-200 text-slate-500 hover:border-slate-300"
              } disabled:cursor-not-allowed disabled:opacity-50`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-400">
          {MOOD_OPTIONS.find((o) => o.value === mood)?.emoji}
        </p>
      </div>

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {!alreadyAnswered && (
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "제출 중..." : "회고 제출"}
        </button>
      )}

      {alreadyAnswered && (
        <p className="text-sm text-green-600 font-medium">
          오늘의 회고가 이미 제출되었습니다.
        </p>
      )}
    </form>
  );
}
