/**
 * BusinessInfo — 전자상거래법 §13 사업자 정보 표시 블록.
 *
 * Legally-required seller disclosure: 상호 / 대표자 / 사업자등록번호 /
 * 주소 / 연락처 / 통신판매업 신고 / 문의 이메일. Values come from
 * NEXT_PUBLIC_BUSINESS_* env vars when present, else reasonable defaults
 * (사업자등록번호 459-01-03808 발급됨, 메모리 business_registration.md).
 *
 * The support email is surfaced prominently with a note that customers who
 * CANNOT log in may still reach support via this address.
 *
 * Pure presentational. v3 tone: hairline-ruled key/value rows, no italic,
 * tokens only.
 */

import * as React from "react";

import {
  businessInfoRaw,
  businessInfoWithDefaults,
  ftcBizInfoUrl,
  SUPPORT_EMAIL_DEFAULT,
} from "@/lib/business-info";

// 단일 SoT 모듈에서 default-적용 값을 읽는다. env 변수명 분기는 SoT 가 흡수한다.
const INFO = businessInfoWithDefaults();
const BUSINESS_NAME = INFO.name;
const BUSINESS_OWNER = INFO.representative;
const BUSINESS_REG_NO = INFO.registrationNumber;
const BUSINESS_ADDRESS = INFO.address;
const BUSINESS_PHONE = INFO.phone;
const BUSINESS_MAILORDER_NO = INFO.telesellerNumber;
const PRIVACY_OFFICER = INFO.privacyOfficer;

export const SUPPORT_EMAIL = INFO.supportEmail || SUPPORT_EMAIL_DEFAULT;

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div
      className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2"
      style={{ borderTop: "0.5px solid var(--pq-ivory-line-soft)" }}
    >
      <span
        className="font-sans text-pq-eyebrow uppercase"
        style={{
          letterSpacing: "0.12em",
          color: "var(--pq-bronze)",
          fontWeight: 500,
        }}
      >
        {label}
      </span>
      <span
        className="font-mono text-pq-caption"
        style={{ color: "var(--pq-ivory-soft)", textAlign: "right" }}
      >
        {value}
      </span>
    </div>
  );
}

export function BusinessInfo() {
  return (
    <section
      className="rounded-[2px] border p-5 sm:p-6"
      style={{
        borderColor: "var(--pq-ivory-line)",
        background: "var(--pq-card-veil)",
      }}
      aria-labelledby="business-info-heading"
    >
      <h2
        id="business-info-heading"
        className="font-sans text-pq-eyebrow uppercase"
        style={{
          letterSpacing: "0.2em",
          color: "var(--pq-bronze)",
          fontWeight: 500,
        }}
      >
        사업자 정보
      </h2>

      <div className="mt-3">
        <InfoRow label="상호" value={BUSINESS_NAME} />
        <InfoRow label="대표자" value={BUSINESS_OWNER} />
        <InfoRow label="개인정보보호책임자" value={PRIVACY_OFFICER} />
        <InfoRow label="사업자등록번호" value={BUSINESS_REG_NO} />
        <InfoRow label="통신판매업 신고" value={BUSINESS_MAILORDER_NO} />
        {/* 공정위 통신판매사업자 조회 링크 — 신고번호 env 가 실제 설정된
            경우에만 노출(default '신고 진행 중' 상태에서는 조회 불가). */}
        {businessInfoRaw.telesellerNumber && ftcBizInfoUrl() && (
          <InfoRow
            label="사업자정보확인"
            value={
              <a
                href={ftcBizInfoUrl()}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "var(--pq-bronze-light)",
                  textDecoration: "underline",
                  textUnderlineOffset: "2px",
                }}
              >
                공정거래위원회 조회
              </a>
            }
          />
        )}
        <InfoRow label="주소" value={BUSINESS_ADDRESS} />
        <InfoRow label="연락처" value={BUSINESS_PHONE} />
        <InfoRow
          label="문의 이메일"
          value={
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              style={{
                color: "var(--pq-bronze-light)",
                textDecoration: "underline",
                textUnderlineOffset: "2px",
              }}
            >
              {SUPPORT_EMAIL}
            </a>
          }
        />
      </div>

      <p
        className="mt-4 font-serif text-pq-caption"
        style={{
          lineHeight: 1.6,
          color: "var(--pq-ivory-dim)",
          wordBreak: "keep-all",
        }}
      >
        로그인이 어려운 고객도 위 이메일 주소로 문의를 보내실 수 있습니다.
      </p>
    </section>
  );
}
