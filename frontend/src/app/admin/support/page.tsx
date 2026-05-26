"use client";

/**
 * /admin/support — 고객문의 운영 콘솔 (operator console).
 *
 * Lists every inquiry (GET /api/support/admin/inquiries[?status=]) with a
 * status filter, expandable detail (full body + prior admin_reply), and a
 * reply composer (POST /api/support/admin/inquiries/<id>/reply). On a
 * successful reply the row flips to "answered" and the new reply is reflected
 * immediately via SWR mutate.
 *
 * Auth: the parent admin/layout.tsx gates the whole tree. The backend also
 * returns 404 to non-admins, which we surface as a "권한 없음" notice.
 *
 * Tone follows the admin area (slate/white). Category/status chips reuse the
 * shared support badges (v3 tokens). No italic, no raw hex, no "AI Coach".
 */

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Inbox, Send, AlertCircle } from "lucide-react";
import { useAdminInquiries, replyToInquiry } from "@/lib/hooks";
import { ApiError } from "@/lib/api";
import { CategoryBadge, StatusBadge } from "@/components/support/support-badges";
import { cn } from "@/lib/utils";
import type { SupportAdminInquiry, SupportStatus } from "@/lib/types";

/* ═══════════════════════ helpers ═══════════════════════ */

type StatusFilter = "all" | SupportStatus;

const STATUS_TABS: ReadonlyArray<{ value: StatusFilter; label: string }> = [
  { value: "all", label: "전체" },
  { value: "open", label: "접수" },
  { value: "answered", label: "답변완료" },
  { value: "closed", label: "종료" },
];

/** KST-pinned absolute datetime so the day doesn't roll for non-KST viewers. */
function fmtKst(iso: string | null | undefined): string {
  if (!iso) return "";
  const needsUtc = !iso.endsWith("Z") && !/[+-]\d{2}:?\d{2}$/.test(iso);
  const d = new Date(needsUtc ? iso + "Z" : iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Seoul",
  });
}

/* ═══════════════════════ page ═══════════════════════ */

export default function AdminSupportPage() {
  const [filter, setFilter] = useState<StatusFilter>("all");
  const { data, error, isLoading, mutate } = useAdminInquiries(
    filter === "all" ? undefined : filter,
  );

  const inquiries = useMemo(() => data?.inquiries ?? [], [data]);

  // A 404 from the backend means "not an admin" (the layout already gates the
  // tree, but the API enforces it independently). Any other error is a load
  // failure.
  const isPermissionError = error instanceof ApiError && error.status === 404;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 md:px-6 md:py-10">
      {/* ── Intro ── */}
      <section className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">
          고객문의
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          접수된 1:1 문의를 확인하고 답변을 보냅니다. 답변을 보내면 작성자에게
          이메일이 발송되고 상태가 “답변완료”로 바뀝니다.
        </p>
      </section>

      {/* ── Status filter ── */}
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <div className="flex items-center rounded-md border border-slate-200 bg-white p-0.5 text-xs">
          {STATUS_TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setFilter(t.value)}
              className={cn(
                "rounded px-3 py-1 font-medium transition-colors",
                filter === t.value
                  ? "bg-slate-900 text-white"
                  : "text-slate-500 hover:text-slate-900",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Permission error ── */}
      {isPermissionError && (
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
          <AlertCircle className="h-4 w-4 shrink-0 text-slate-400" />
          권한이 없습니다.
        </div>
      )}

      {/* ── Load error (non-404) ── */}
      {error && !isPermissionError && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <span>문의 목록을 불러오지 못했습니다.</span>
          <button
            type="button"
            onClick={() => void mutate()}
            className="rounded-md border border-red-300 px-3 py-1 text-xs font-medium text-red-700 transition-colors hover:bg-red-100"
          >
            다시 시도
          </button>
        </div>
      )}

      {/* ── Loading ── */}
      {isLoading && !data && !error && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      )}

      {/* ── Empty ── */}
      {!isLoading && !error && inquiries.length === 0 && (
        <div className="rounded-lg border border-slate-200 bg-white px-6 py-12 text-center">
          <Inbox className="mx-auto h-7 w-7 text-slate-300" aria-hidden="true" />
          <p className="mt-3 text-sm text-slate-500">문의 없음</p>
        </div>
      )}

      {/* ── List ── */}
      {!error && inquiries.length > 0 && (
        <div className="space-y-3">
          {inquiries.map((item) => (
            <InquiryItem key={item.id} item={item} statusFilter={filter} mutate={mutate} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════ row ═══════════════════════ */

function InquiryItem({
  item,
  statusFilter,
  mutate,
}: {
  item: SupportAdminInquiry;
  statusFilter: StatusFilter;
  mutate: () => Promise<unknown>;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* Header (click to expand) */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50"
        aria-expanded={expanded}
      >
        <span className="mt-1 shrink-0 text-slate-400">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <CategoryBadge category={item.category} />
            <StatusBadge status={item.status} />
          </div>
          <p className="mt-1.5 truncate text-sm font-semibold text-slate-900">
            #{item.id} · {item.subject}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            {item.email_snapshot} · {fmtKst(item.created_at)}
          </p>
          {!expanded && (
            <p className="mt-1 line-clamp-1 text-xs text-slate-400">{item.body}</p>
          )}
        </div>
      </button>

      {/* Detail + reply */}
      {expanded && (
        <div className="border-t border-slate-100 px-4 py-4">
          {/* Full body */}
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
              문의 내용
            </p>
            <p className="mt-1.5 whitespace-pre-wrap break-words text-sm text-slate-700">
              {item.body}
            </p>
          </div>

          {/* Existing reply, if any */}
          {item.admin_reply && (
            <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
                기존 답변
                {item.answered_at ? ` · ${fmtKst(item.answered_at)}` : ""}
              </p>
              <p className="mt-1.5 whitespace-pre-wrap break-words text-sm text-slate-700">
                {item.admin_reply}
              </p>
            </div>
          )}

          <ReplyComposer item={item} statusFilter={statusFilter} mutate={mutate} />
        </div>
      )}
    </article>
  );
}

/* ═══════════════════════ reply composer ═══════════════════════ */

function ReplyComposer({
  item,
  statusFilter,
  mutate,
}: {
  item: SupportAdminInquiry;
  statusFilter: StatusFilter;
  mutate: () => Promise<unknown>;
}) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const trimmed = draft.trim();
  const canSend = trimmed.length > 0 && !sending;

  const onSend = async () => {
    if (!canSend) return;
    setSending(true);
    setErr(null);
    try {
      await replyToInquiry(item.id, trimmed);
      setDraft("");
      // Refresh the current filter's list. If the active filter would exclude
      // the now-"answered" row, mutate drops it; otherwise the row updates in
      // place. Either way the operator sees a consistent state.
      void statusFilter;
      await mutate();
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        if (e.status === 404) {
          setErr("권한이 없거나 문의를 찾을 수 없습니다.");
        } else if (e.status === 400) {
          setErr("답변은 1~5000자여야 합니다.");
        } else {
          setErr("답변 전송에 실패했습니다. 잠시 후 다시 시도해 주세요.");
        }
      } else {
        setErr("답변 전송에 실패했습니다. 잠시 후 다시 시도해 주세요.");
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mt-4">
      <label
        htmlFor={`reply-${item.id}`}
        className="text-xs font-medium uppercase tracking-wider text-slate-400"
      >
        답변 작성
      </label>
      <p className="mt-1 text-xs text-slate-400">
        투자 자문·권유성 표현은 사용하지 마세요. 결제·계정·사용법 안내만
        작성합니다.
      </p>
      <textarea
        id={`reply-${item.id}`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={4}
        maxLength={5000}
        placeholder="답변을 입력하세요…"
        className="mt-2 w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
      />
      {err && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-red-600">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          {err}
        </p>
      )}
      <div className="mt-2 flex items-center justify-end gap-3">
        <span className="text-xs text-slate-400">{trimmed.length}/5000</span>
        <button
          type="button"
          onClick={() => void onSend()}
          disabled={!canSend}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition-colors",
            canSend
              ? "bg-slate-900 text-white hover:bg-slate-800"
              : "cursor-not-allowed bg-slate-200 text-slate-400",
          )}
        >
          <Send className="h-3.5 w-3.5" />
          {sending ? "전송 중…" : "답변 전송"}
        </button>
      </div>
    </div>
  );
}
