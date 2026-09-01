"use client";

/**
 * /support/inbox — 내 문의함 (로그인).
 *
 * useSWR(GET /api/support/inquiries) 목록: 카테고리 배지 + 제목 + status
 * 배지 + 작성일(KST). 클릭 → /support/inbox/[id] 상세. 빈 상태 CTA.
 *
 * v3 tone. DisclaimerBanner 는 layout 이 하단 마운트.
 */

import { useCallback } from "react";
import Link from "next/link";
import { Inbox, ChevronRight } from "lucide-react";
import { useSupportInquiries } from "@/lib/hooks";
import { CategoryBadge, StatusBadge } from "@/components/support/support-badges";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import {
  RuledKicker,
  EditorialHead,
  Caption,
  FootSignature,
} from "@/components/ui/editorial";
import type { SupportInquiryListItem } from "@/lib/types";

/** KST-pinned absolute date so the day doesn't roll for non-KST viewers. */
export function inquiryDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const needsUtc = !iso.endsWith("Z") && !/[+-]\d{2}:?\d{2}$/.test(iso);
  const d = new Date(needsUtc ? iso + "Z" : iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "Asia/Seoul",
  });
}

function InquiryRow({ item }: { item: SupportInquiryListItem }) {
  return (
    <Link
      href={`/support/inbox/${item.id}`}
      className="flex items-center gap-3 rounded-[2px] border p-4 transition-colors hover:bg-[var(--pq-card-veil-strong)]"
      style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <CategoryBadge category={item.category} />
          <StatusBadge status={item.status} />
        </div>
        <p
          className="mt-2 truncate font-display text-pq-h6"
          style={{ color: "var(--pq-ivory)", letterSpacing: "-0.01em" }}
        >
          {item.subject}
        </p>
        <p className="mt-1 font-mono text-pq-caption" style={{ color: "var(--pq-ivory-faint)" }}>
          {inquiryDate(item.created_at)}
        </p>
      </div>
      <ChevronRight className="h-4 w-4 shrink-0" style={{ color: "var(--pq-muted)" }} />
    </Link>
  );
}

function LoadingState() {
  return (
    <div className="space-y-3" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-24 animate-pulse rounded-[2px] border"
          style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
        />
      ))}
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
        문의 목록을 불러오지 못했습니다.
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

function EmptyState() {
  return (
    <div
      className="rounded-[2px] border px-6 py-12 text-center"
      style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
    >
      <Inbox className="mx-auto h-7 w-7" style={{ color: "var(--pq-bronze-light)" }} aria-hidden="true" />
      <p
        className="mx-auto mt-4 max-w-md font-serif text-pq-h6"
        style={{ lineHeight: 1.6, color: "var(--pq-ivory-soft)", wordBreak: "keep-all" }}
      >
        아직 접수한 문의가 없습니다.
      </p>
      <Caption className="mx-auto mt-2 max-w-md">
        결제·계정·사용법 문의를 1:1 문의로 남기시면 담당자가 확인 후
        답변드립니다.
      </Caption>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                <Link
          href="/support/contact"
          className="inline-flex items-center gap-2 rounded-[2px] border px-5 py-2.5 font-mono text-pq-caption uppercase tracking-[0.16em] transition-colors hover:bg-[var(--pq-card-veil-strong)]"
          style={{ borderColor: "var(--pq-ivory-line)", color: "var(--pq-ivory-soft)" }}
        >
          1:1 문의하기
        </Link>
      </div>
    </div>
  );
}

function InboxContent() {
  const { data, isLoading, error, mutate } = useSupportInquiries();
  const retry = useCallback(() => {
    void mutate();
  }, [mutate]);

  const inquiries = data?.inquiries ?? [];

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
      <header className="mb-6">
        <RuledKicker>Inbox</RuledKicker>
        <EditorialHead as="h1" size={32} className="mt-3">
          내 문의함
        </EditorialHead>
        <Caption className="mt-2 max-w-lg">
          접수한 1:1 문의와 답변 내역입니다.
        </Caption>
      </header>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <LoadFailure onRetry={retry} />
      ) : inquiries.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-3">
          {inquiries.map((item) => (
            <InquiryRow key={item.id} item={item} />
          ))}
        </div>
      )}

      <FootSignature />
    </div>
  );
}

export default function SupportInboxPage() {
  return (
    <ErrorBoundary>
      <InboxContent />
    </ErrorBoundary>
  );
}
