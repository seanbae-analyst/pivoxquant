"use client";

/**
 * /support/contact — 1:1 문의하기 (로그인).
 *
 * category(4) + 제목(≤200) + 내용(≤5000, 글자수 카운터) + PIPA 수집 고지.
 * 제출 → POST /api/support/inquiries. 성공 시 인라인 성공 + 폼 리셋 +
 * 내 문의함 안내 + 목록 mutate. 429/401/400 분기.
 *
 * 상단에 "먼저 AI 고객지원에게 물어보면 더 빨라요" → /support/chat 링크.
 *
 * v3 tone. DisclaimerBanner 는 (dashboard)/layout.tsx 가 하단에 1회 마운트.
 */

import { useState, useCallback } from "react";
import Link from "next/link";
import { useSWRConfig } from "swr";
import { MessageSquare, CheckCircle2, ArrowRight } from "lucide-react";
import { API } from "@/lib/endpoints";
import { createSupportInquiry } from "@/lib/hooks";
import { ApiError } from "@/lib/api";
import { SUPPORT_CATEGORY_OPTIONS } from "@/components/support/support-meta";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  RuledKicker,
  EditorialHead,
  Caption,
  FieldLabel,
  FootSignature,
} from "@/components/ui/editorial";
import type { SupportCategory } from "@/lib/types";

const SUBJECT_MAX = 200;
const BODY_MAX = 5000;

type SubmitState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success" }
  | { kind: "error"; message: string };

function errorMessageFor(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429) return "문의가 너무 많습니다. 잠시 후 다시 시도해 주세요.";
    if (err.status === 401) return "로그인이 필요합니다. 다시 로그인해 주세요.";
    if (err.status === 400) return "입력 내용을 확인해 주세요. 제목과 내용을 모두 입력해야 합니다.";
  }
  return "문의 접수 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.";
}

function ContactForm() {
  const { mutate } = useSWRConfig();
  const [category, setCategory] = useState<SupportCategory>("billing");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [state, setState] = useState<SubmitState>({ kind: "idle" });

  const submitting = state.kind === "submitting";
  const canSubmit =
    !submitting &&
    subject.trim().length > 0 &&
    body.trim().length > 0 &&
    subject.length <= SUBJECT_MAX &&
    body.length <= BODY_MAX;

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!canSubmit) return;
      setState({ kind: "submitting" });
      try {
        await createSupportInquiry({
          category,
          subject: subject.trim(),
          body: body.trim(),
        });
        // Refresh the inbox list cache so the new inquiry is visible.
        await mutate(API.support.inquiries);
        setState({ kind: "success" });
        setSubject("");
        setBody("");
        setCategory("billing");
      } catch (err) {
        setState({ kind: "error", message: errorMessageFor(err) });
      }
    },
    [canSubmit, category, subject, body, mutate],
  );

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
      {/* Header */}
      <header className="mb-6">
        <RuledKicker>Contact</RuledKicker>
        <EditorialHead as="h1" size={32} className="mt-3">
          1:1 문의하기
        </EditorialHead>
        <Caption className="mt-2 max-w-lg">
          결제·계정·기술 문의를 남겨 주세요. 접수한 문의와 답변은 내 문의함에서
          확인할 수 있습니다.
        </Caption>
      </header>

      {/* AI shortcut hint */}
      <Link
        href="/support/chat"
        className="mb-6 flex items-center gap-2 rounded-[2px] border px-4 py-3 transition-colors hover:bg-[var(--pq-card-veil-strong)]"
        style={{
          borderColor: "var(--pq-ivory-line)",
          background: "var(--pq-card-veil)",
        }}
      >
        <MessageSquare className="h-4 w-4 shrink-0" style={{ color: "var(--pq-bronze)" }} />
        <span className="font-serif text-pq-caption" style={{ color: "var(--pq-ivory-soft)" }}>
          먼저 AI 고객지원에게 물어보면 더 빨라요
        </span>
        <ArrowRight className="ml-auto h-3.5 w-3.5 shrink-0" style={{ color: "var(--pq-muted)" }} />
      </Link>

      {/* Success banner */}
      {state.kind === "success" && (
        <div
          className="mb-6 flex items-start gap-3 rounded-[2px] border p-4"
          style={{ borderColor: "var(--pq-bronze)", background: "var(--pq-card-veil)" }}
          role="status"
        >
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" style={{ color: "var(--pq-bronze)" }} />
          <div>
            <p className="font-serif text-pq-lead" style={{ color: "var(--pq-ivory)" }}>
              문의가 접수되었습니다.
            </p>
            <p className="mt-1 font-serif text-pq-caption" style={{ color: "var(--pq-ivory-dim)" }}>
              답변이 등록되면{" "}
              <Link
                href="/support/inbox"
                style={{ color: "var(--pq-bronze-light)", textDecoration: "underline", textUnderlineOffset: "2px" }}
              >
                내 문의함
              </Link>
              에서 확인할 수 있습니다.
            </p>
          </div>
        </div>
      )}

      {/* Error banner */}
      {state.kind === "error" && (
        <div
          className="mb-6 rounded-[2px] border p-4"
          style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
          role="alert"
        >
          <p className="font-serif text-pq-caption" style={{ color: "var(--pq-negative)" }}>
            {state.message}
          </p>
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Category */}
        <div>
          <FieldLabel>문의 유형</FieldLabel>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as SupportCategory)}
            disabled={submitting}
            className="mt-2 w-full rounded-[2px] border bg-transparent px-3 py-2.5 font-sans text-pq-lead"
            style={{
              borderColor: "var(--pq-ivory-line)",
              color: "var(--pq-ivory)",
              background: "var(--pq-card-veil)",
            }}
          >
            {SUPPORT_CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} style={{ background: "var(--pq-onyx)" }}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Subject */}
        <div>
          <div className="flex items-baseline justify-between">
            <FieldLabel>제목</FieldLabel>
            <span
              className="font-mono text-pq-caption"
              style={{ color: subject.length > SUBJECT_MAX ? "var(--pq-negative)" : "var(--pq-ivory-faint)" }}
            >
              {subject.length} / {SUBJECT_MAX}
            </span>
          </div>
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            maxLength={SUBJECT_MAX}
            disabled={submitting}
            placeholder="문의 제목을 입력해 주세요"
            className="mt-2 w-full rounded-[2px] border bg-transparent px-3 py-2.5 font-sans text-pq-lead"
            style={{
              borderColor: "var(--pq-ivory-line)",
              color: "var(--pq-ivory)",
              background: "var(--pq-card-veil)",
            }}
          />
        </div>

        {/* Body */}
        <div>
          <div className="flex items-baseline justify-between">
            <FieldLabel>문의 내용</FieldLabel>
            <span
              className="font-mono text-pq-caption"
              style={{ color: body.length > BODY_MAX ? "var(--pq-negative)" : "var(--pq-ivory-faint)" }}
            >
              {body.length} / {BODY_MAX}
            </span>
          </div>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={BODY_MAX}
            disabled={submitting}
            rows={8}
            placeholder="문의 내용을 자세히 적어 주세요. 결제 관련 문의는 결제 내역도 함께 남겨 주시면 빠릅니다."
            className="mt-2 w-full resize-y rounded-[2px] border bg-transparent px-3 py-2.5 font-sans text-pq-lead"
            style={{
              borderColor: "var(--pq-ivory-line)",
              color: "var(--pq-ivory)",
              background: "var(--pq-card-veil)",
              lineHeight: 1.6,
            }}
          />
        </div>

        {/* PIPA collection notice */}
        <p
          className="font-serif text-pq-caption"
          style={{ color: "var(--pq-ivory-dim)", lineHeight: 1.6, wordBreak: "keep-all" }}
        >
          문의 처리를 위해 이메일·문의내용이 수집됩니다. 수집된 정보는
          개인정보처리방침에 따라 문의 응대 목적으로만 이용됩니다.
        </p>

        {/* Submit */}
        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full rounded-[2px] border px-5 py-3 font-mono text-pq-caption uppercase tracking-[0.16em] transition-colors disabled:cursor-not-allowed disabled:opacity-40 hover:bg-[var(--pq-card-veil-strong)]"
          style={{
            borderColor: "var(--pq-bronze)",
            color: "var(--pq-bronze)",
            background: "var(--pq-card-veil)",
          }}
        >
          {submitting ? "접수 중…" : "문의 접수하기"}
        </button>
      </form>

      <FootSignature />
    </div>
  );
}

export default function SupportContactPage() {
  return (
    <ErrorBoundary>
      <ContactForm />
    </ErrorBoundary>
  );
}
