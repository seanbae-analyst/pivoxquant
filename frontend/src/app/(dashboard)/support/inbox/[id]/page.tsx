"use client";

/**
 * /support/inbox/[id] — 문의 상세 (로그인).
 *
 * useSWR(GET /api/support/inquiries/:id): 원문 + admin_reply(없으면 "답변
 * 대기 중"). id 는 useParams 의 string 을 그대로 사용 — 백엔드 <int:iid>
 * 파싱. v3 tone. DisclaimerBanner 는 layout 이 하단 마운트.
 */

import { useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronLeft, Clock3, MessageCircleReply } from "lucide-react";
import { useSupportInquiry } from "@/lib/hooks";
import { CategoryBadge, StatusBadge } from "@/components/support/support-badges";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EditorialHead, FieldLabel, FootSignature } from "@/components/ui/editorial";
import { inquiryDate } from "../page";

function BackLink() {
  return (
    <Link
      href="/support/inbox"
      className="mb-6 inline-flex items-center gap-1.5 font-sans text-pq-caption transition-colors"
      style={{ color: "var(--pq-ivory-dim)" }}
    >
      <ChevronLeft className="h-4 w-4" />
      내 문의함
    </Link>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4" aria-hidden="true">
      <div
        className="h-40 animate-pulse rounded-[2px] border"
        style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
      />
      <div
        className="h-32 animate-pulse rounded-[2px] border"
        style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
      />
    </div>
  );
}

function LoadFailure({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      className="rounded-[2px] border p-6 text-center"
      style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
    >
      <p className="font-serif text-pq-mono-sm" style={{ color: "var(--pq-ivory-soft)" }}>
        문의를 불러오지 못했습니다.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded-[2px] border px-4 py-2 font-mono text-pq-caption uppercase tracking-[0.16em] transition-colors hover:bg-[var(--pq-card-veil-strong)]"
        style={{ borderColor: "var(--pq-ivory-line)", color: "var(--pq-bronze-light)" }}
      >
        다시 시도
      </button>
    </div>
  );
}

function DetailContent() {
  const params = useParams<{ id: string }>();
  // useParams returns string | string[]; the dynamic segment is a single
  // string. Pass through verbatim — the backend parses <int:iid>.
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { data, isLoading, error, mutate } = useSupportInquiry(id);
  const retry = useCallback(() => {
    void mutate();
  }, [mutate]);

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
      <BackLink />

      {isLoading ? (
        <LoadingState />
      ) : error || !data ? (
        <LoadFailure onRetry={retry} />
      ) : (
        <>
          {/* Inquiry header */}
          <div className="flex flex-wrap items-center gap-2">
            <CategoryBadge category={data.category} />
            <StatusBadge status={data.status} />
          </div>
          <EditorialHead as="h1" size={30} className="mt-3" style={{ wordBreak: "keep-all" }}>
            {data.subject}
          </EditorialHead>
          <p className="mt-2 font-mono text-pq-caption" style={{ color: "var(--pq-ivory-faint)" }}>
            접수일 {inquiryDate(data.created_at)}
          </p>

          {/* Original body */}
          <section
            className="mt-6 rounded-[2px] border p-5"
            style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
          >
            <FieldLabel>문의 내용</FieldLabel>
            <p
              className="mt-3 font-serif text-pq-lead"
              style={{
                lineHeight: 1.7,
                color: "var(--pq-ivory-soft)",
                whiteSpace: "pre-wrap",
                wordBreak: "keep-all",
              }}
            >
              {data.body}
            </p>
          </section>

          {/* Admin reply or pending */}
          {data.admin_reply && data.admin_reply.trim().length > 0 ? (
            <section
              className="mt-4 rounded-[2px] border p-5"
              style={{ borderColor: "var(--pq-bronze)", background: "var(--pq-card-veil)" }}
            >
              <div className="flex items-center gap-2">
                <MessageCircleReply className="h-4 w-4" style={{ color: "var(--pq-bronze)" }} />
                <FieldLabel>답변</FieldLabel>
                {data.answered_at && (
                  <span className="ml-auto font-mono text-pq-caption" style={{ color: "var(--pq-ivory-faint)" }}>
                    {inquiryDate(data.answered_at)}
                  </span>
                )}
              </div>
              <p
                className="mt-3 font-serif text-pq-lead"
                style={{
                  lineHeight: 1.7,
                  color: "var(--pq-ivory)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "keep-all",
                }}
              >
                {data.admin_reply}
              </p>
            </section>
          ) : (
            <section
              className="mt-4 flex items-center gap-3 rounded-[2px] border p-5"
              style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
            >
              <Clock3 className="h-4 w-4 shrink-0" style={{ color: "var(--pq-muted)" }} />
              <p className="font-serif text-pq-lead" style={{ color: "var(--pq-ivory-dim)" }}>
                답변 대기 중입니다. 답변이 등록되면 이곳에 표시됩니다.
              </p>
            </section>
          )}
        </>
      )}

      <FootSignature />
    </div>
  );
}

export default function SupportInquiryDetailPage() {
  return (
    <ErrorBoundary>
      <DetailContent />
    </ErrorBoundary>
  );
}
