"use client";

/**
 * /support/chat — AI 고객지원 (로그인).
 *
 * "AI 고객지원" — 결제·계정·사용법 도우미. 투자 상담은 제공하지 않는다.
 * ("AI Coach / 투자 코치" 금지 — 자본시장법.)
 *
 * 봇 인사 1개. user(bronze) · bot(card surface) 버블. textarea(maxLength
 * 2000) + 전송. Enter 전송 / Shift+Enter 줄바꿈. 전송 시 직전 history(≤10턴,
 * 정상 턴만 — error/guidance 버블 제외) 동봉 POST. 대기중 "입력 중…".
 * escalated && inquiry_id>0 → 봇 버블 아래 "상담 접수됨" 카드(→ 내 문의함).
 * 429 / 401 / 400 분기 버블. 빈·공백 차단 + 전송중 중복방지.
 *
 * DisclaimerBanner 는 (dashboard)/layout.tsx 가 /support → "signal" 변형이
 * 아닌 기본 변형으로 하단 1회 마운트한다 (PATH_TO_TYPE 미매칭 → 기본 signal).
 */

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import { SendHorizonal, Inbox } from "lucide-react";
import { sendSupportChat } from "@/lib/hooks";
import { ApiError } from "@/lib/api";
import { StatusBadge } from "@/components/support/support-badges";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { RuledKicker, EditorialHead, Caption } from "@/components/ui/editorial";
import type { SupportChatMessage } from "@/lib/types";

const MESSAGE_MAX = 2000;

/**
 * Bubble kind:
 *   - "user" / "bot": normal conversation turns (eligible for history).
 *   - "guidance": the seeded bot intro + 401/400 hints (NOT sent as history).
 *   - "error": transient failures (NOT sent as history).
 */
type BubbleKind = "user" | "bot" | "guidance" | "error";

interface Bubble {
  id: number;
  kind: BubbleKind;
  text: string;
  /** Set on bot bubbles that escalated to a 1:1 inquiry. */
  escalatedInquiryId?: number;
}

const INTRO: Bubble = {
  id: 0,
  kind: "guidance",
  text:
    "안녕하세요, AI 고객지원입니다. 결제·계정·사용법에 대해 도와드려요. 투자 상담은 제공하지 않습니다. 무엇을 도와드릴까요?",
};

let bubbleSeq = 1;
function nextId(): number {
  return bubbleSeq++;
}

/** Normal turns only (user/bot), capped at 10, mapped to the wire shape. */
function toHistory(bubbles: Bubble[]): SupportChatMessage[] {
  return bubbles
    .filter((b) => b.kind === "user" || b.kind === "bot")
    .slice(-10)
    .map((b) => ({
      role: b.kind === "user" ? ("user" as const) : ("assistant" as const),
      content: b.text,
    }));
}

function errorBubbleText(err: unknown): { kind: BubbleKind; text: string } {
  if (err instanceof ApiError) {
    if (err.status === 429)
      return { kind: "error", text: "문의가 잠시 많습니다. 잠시 후 다시 시도해 주세요." };
    if (err.status === 401)
      return { kind: "guidance", text: "세션이 만료되었습니다. 다시 로그인한 뒤 이용해 주세요." };
    if (err.status === 400)
      return { kind: "guidance", text: "메시지를 다시 확인해 주세요. (1~2000자)" };
  }
  return { kind: "error", text: "응답을 받지 못했습니다. 잠시 후 다시 시도해 주세요." };
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div
        className="max-w-[85%] rounded-[2px] px-4 py-2.5"
        style={{
          background: "color-mix(in srgb, var(--pq-bronze) 16%, transparent)",
          border: "0.5px solid var(--pq-bronze)",
        }}
      >
        <p
          className="font-sans text-pq-lead"
          style={{ color: "var(--pq-ivory)", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "keep-all" }}
        >
          {text}
        </p>
      </div>
    </div>
  );
}

function BotBubble({ bubble }: { bubble: Bubble }) {
  return (
    <div className="flex flex-col items-start gap-2">
      <div
        className="max-w-[85%] rounded-[2px] px-4 py-2.5"
        style={{ background: "var(--pq-card-veil)", border: "0.5px solid var(--pq-ivory-line)" }}
      >
        <p
          className="font-serif text-pq-lead"
          style={{ color: "var(--pq-ivory-soft)", lineHeight: 1.7, whiteSpace: "pre-wrap", wordBreak: "keep-all" }}
        >
          {bubble.text}
        </p>
      </div>
      {typeof bubble.escalatedInquiryId === "number" && bubble.escalatedInquiryId > 0 && (
        <Link
          href={`/support/inbox/${bubble.escalatedInquiryId}`}
          className="flex items-center gap-2 rounded-[2px] border px-3 py-2 transition-colors hover:bg-[var(--pq-card-veil-strong)]"
          style={{ borderColor: "var(--pq-bronze)", background: "var(--pq-card-veil)" }}
        >
          <Inbox className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--pq-bronze)" }} />
          <span className="font-sans text-pq-caption" style={{ color: "var(--pq-ivory)" }}>
            상담 접수됨 — 내 문의함에서 보기
          </span>
          <span className="font-mono text-pq-caption" style={{ color: "var(--pq-ivory-faint)" }}>
            #{bubble.escalatedInquiryId}
          </span>
          <StatusBadge status="open" />
        </Link>
      )}
    </div>
  );
}

function NoteBubble({ bubble }: { bubble: Bubble }) {
  const isError = bubble.kind === "error";
  return (
    <div className="flex justify-start">
      <div
        className="max-w-[85%] rounded-[2px] px-4 py-2.5"
        style={{
          background: "var(--pq-card-veil)",
          border: `0.5px solid ${isError ? "var(--pq-negative)" : "var(--pq-ivory-line)"}`,
        }}
      >
        <p
          className="font-serif text-pq-caption"
          style={{ color: isError ? "var(--pq-negative)" : "var(--pq-ivory-dim)", lineHeight: 1.6, wordBreak: "keep-all" }}
        >
          {bubble.text}
        </p>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div
        className="rounded-[2px] px-4 py-2.5"
        style={{ background: "var(--pq-card-veil)", border: "0.5px solid var(--pq-ivory-line)" }}
      >
        <span className="font-mono text-pq-caption" style={{ color: "var(--pq-ivory-dim)" }}>
          입력 중…
        </span>
      </div>
    </div>
  );
}

function ChatContent() {
  const [bubbles, setBubbles] = useState<Bubble[]>([INTRO]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to the newest bubble / typing indicator.
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [bubbles, pending]);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || pending) return; // empty/whitespace + in-flight dup guard

    // Snapshot history from the EXISTING normal turns (before this message).
    const history = toHistory(bubbles);

    const userBubble: Bubble = { id: nextId(), kind: "user", text };
    setBubbles((prev) => [...prev, userBubble]);
    setDraft("");
    setPending(true);

    try {
      const res = await sendSupportChat(text, history);
      const botBubble: Bubble = {
        id: nextId(),
        kind: "bot",
        text: res.reply,
        escalatedInquiryId:
          res.escalated && typeof res.inquiry_id === "number" && res.inquiry_id > 0
            ? res.inquiry_id
            : undefined,
      };
      setBubbles((prev) => [...prev, botBubble]);
    } catch (err) {
      const { kind, text: msg } = errorBubbleText(err);
      setBubbles((prev) => [...prev, { id: nextId(), kind, text: msg }]);
    } finally {
      setPending(false);
    }
  }, [draft, pending, bubbles]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter sends; Shift+Enter inserts a newline.
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        void send();
      }
    },
    [send],
  );

  const canSend = !pending && draft.trim().length > 0 && draft.length <= MESSAGE_MAX;

  return (
    <div className="mx-auto flex h-[calc(100dvh-4rem)] w-full max-w-2xl flex-col px-4 py-6 sm:px-6">
      {/* Header */}
      <header className="mb-4 shrink-0">
        <RuledKicker>Support Assistant</RuledKicker>
        <EditorialHead as="h1" size={30} className="mt-2">
          AI 고객지원
        </EditorialHead>
        <Caption className="mt-1.5 max-w-lg">
          결제·계정·사용법 문의를 도와드려요. 투자 상담은 제공하지 않습니다.
        </Caption>
      </header>

      {/* Conversation */}
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {bubbles.map((b) => {
          if (b.kind === "user") return <UserBubble key={b.id} text={b.text} />;
          if (b.kind === "bot") return <BotBubble key={b.id} bubble={b} />;
          return <NoteBubble key={b.id} bubble={b} />;
        })}
        {pending && <TypingIndicator />}
        <div ref={scrollRef} />
      </div>

      {/* Composer */}
      <div className="mt-4 shrink-0">
        <div
          className="flex items-end gap-2 rounded-[2px] border p-2"
          style={{ borderColor: "var(--pq-ivory-line)", background: "var(--pq-card-veil)" }}
        >
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={MESSAGE_MAX}
            rows={1}
            placeholder="메시지를 입력하세요. (Enter 전송 · Shift+Enter 줄바꿈)"
            className="max-h-40 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-2 font-sans text-pq-lead"
            style={{ color: "var(--pq-ivory)", lineHeight: 1.6, outline: "none" }}
            disabled={pending}
            aria-label="문의 메시지"
          />
          <button
            type="button"
            onClick={() => void send()}
            disabled={!canSend}
            aria-label="전송"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[2px] border transition-colors disabled:cursor-not-allowed disabled:opacity-40 hover:bg-[var(--pq-card-veil-strong)]"
            style={{ borderColor: "var(--pq-bronze)", color: "var(--pq-bronze)" }}
          >
            <SendHorizonal className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-1 flex justify-end">
          <span
            className="font-mono text-pq-caption"
            style={{ color: draft.length > MESSAGE_MAX ? "var(--pq-negative)" : "var(--pq-ivory-faint)" }}
          >
            {draft.length} / {MESSAGE_MAX}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function SupportChatPage() {
  return (
    <ErrorBoundary>
      <ChatContent />
    </ErrorBoundary>
  );
}
