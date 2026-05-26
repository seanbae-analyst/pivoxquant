"use client";

/**
 * /support — 고객지원 (public, 비로그인 접근 가능).
 *
 * 공개 진입점: FAQ 아코디언 + 전자상거래법 §13 사업자 정보 블록 + 문의 채널
 * 안내. 로그인 유저는 AI 고객지원 / 1:1 문의 / 내 문의함 CTA 를 보고, 비로그인
 * 유저는 로그인 유도 + 이메일 문의 안내를 본다.
 *
 * 이 라우트는 (dashboard) 그룹 밖이므로 페이지 레벨 DisclaimerBanner 가 자동
 * 마운트되지 않는다. 본 페이지는 분석/시그널 surface 가 아닌 정보·지원 안내
 * 페이지이지만, §101 면책 한 줄을 FAQ 내부에 명시해 둔다.
 *
 * v3 tone: Vantablack + Bronze + Playfair UPRIGHT, KR. italic/raw-hex 금지.
 */

import Link from "next/link";
import { MessageSquare, FileText, Inbox, ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { EditorialHead, RuledKicker, Caption } from "@/components/ui/editorial";
import { FaqSection } from "@/components/support/faq-section";
import { BusinessInfo, SUPPORT_EMAIL } from "@/components/support/business-info";

function PrimaryCta({
  href,
  icon,
  children,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between gap-3 rounded-[2px] border px-5 py-4 transition-colors hover:bg-[var(--pq-card-veil-strong)]"
      style={{
        borderColor: "var(--pq-bronze)",
        background: "var(--pq-card-veil)",
      }}
    >
      <span className="flex items-center gap-3">
        <span style={{ color: "var(--pq-bronze)" }}>{icon}</span>
        <span
          className="font-sans text-pq-lead"
          style={{ color: "var(--pq-ivory)" }}
        >
          {children}
        </span>
      </span>
      <ArrowRight className="h-4 w-4 shrink-0" style={{ color: "var(--pq-bronze)" }} />
    </Link>
  );
}

function SecondaryCta({
  href,
  icon,
  children,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between gap-3 rounded-[2px] border px-5 py-4 transition-colors hover:bg-[var(--pq-card-veil-strong)]"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
    >
      <span className="flex items-center gap-3">
        <span style={{ color: "var(--pq-muted)" }}>{icon}</span>
        <span
          className="font-sans text-pq-lead"
          style={{ color: "var(--pq-ivory)" }}
        >
          {children}
        </span>
      </span>
      <ArrowRight className="h-4 w-4 shrink-0" style={{ color: "var(--pq-muted)" }} />
    </Link>
  );
}

export default function SupportPage() {
  const { user, loading } = useAuth();
  const isAuthed = !loading && !!user;

  return (
    <main
      className="min-h-[100dvh]"
      style={{ background: "var(--pq-ink)", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto w-full max-w-2xl px-4 py-10 sm:px-6 sm:py-14">
        {/* Header */}
        <header className="mb-8">
          <RuledKicker>Support</RuledKicker>
          <EditorialHead as="h1" size={36} className="mt-3">
            고객지원
          </EditorialHead>
          <Caption className="mt-2 max-w-lg">
            결제·계정·사용법에 대한 안내와 문의 채널입니다. 아래 자주 묻는
            질문에서 답을 찾지 못하면 문의를 남겨 주세요.
          </Caption>
        </header>

        {/* Contact channels */}
        <section className="mb-12" aria-labelledby="support-channels-heading">
          <h2
            id="support-channels-heading"
            className="font-sans text-pq-eyebrow uppercase"
            style={{
              letterSpacing: "0.2em",
              color: "var(--pq-bronze)",
              fontWeight: 500,
              marginBottom: 12,
            }}
          >
            문의 채널
          </h2>

          {isAuthed ? (
            <div className="space-y-3">
              <PrimaryCta href="/support/chat" icon={<MessageSquare className="h-5 w-5" />}>
                AI 고객지원에게 물어보기
              </PrimaryCta>
              <SecondaryCta href="/support/contact" icon={<FileText className="h-5 w-5" />}>
                1:1 문의하기
              </SecondaryCta>
              <SecondaryCta href="/support/inbox" icon={<Inbox className="h-5 w-5" />}>
                내 문의함
              </SecondaryCta>
            </div>
          ) : (
            <div
              className="rounded-[2px] border p-5"
              style={{
                borderColor: "var(--pq-ivory-line)",
                background: "var(--pq-card-veil)",
              }}
            >
              <p
                className="font-serif text-pq-lead"
                style={{ color: "var(--pq-ivory-soft)", lineHeight: 1.6, wordBreak: "keep-all" }}
              >
                로그인하면 AI 고객지원에게 바로 질문하거나 1:1 문의를 접수할 수
                있습니다.
              </p>
              <Link
                href="/login"
                className="mt-4 inline-flex items-center gap-2 rounded-[2px] border px-5 py-2.5 font-mono text-pq-caption uppercase tracking-[0.16em] transition-colors hover:bg-[var(--pq-card-veil-strong)]"
                style={{ borderColor: "var(--pq-bronze)", color: "var(--pq-bronze)" }}
              >
                로그인
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <p
                className="mt-4 font-serif text-pq-caption"
                style={{ color: "var(--pq-ivory-dim)", lineHeight: 1.6, wordBreak: "keep-all" }}
              >
                로그인이 어려우시면{" "}
                <a
                  href={`mailto:${SUPPORT_EMAIL}`}
                  style={{
                    color: "var(--pq-bronze-light)",
                    textDecoration: "underline",
                    textUnderlineOffset: "2px",
                  }}
                >
                  {SUPPORT_EMAIL}
                </a>{" "}
                으로 문의해 주세요.
              </p>
            </div>
          )}
        </section>

        {/* FAQ */}
        <div className="mb-12">
          <FaqSection />
        </div>

        {/* Business info (전자상거래법 §13) */}
        <BusinessInfo />
      </div>
    </main>
  );
}
