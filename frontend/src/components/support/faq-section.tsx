/**
 * FaqSection — 자주 묻는 질문 (native <details> 아코디언).
 *
 * 4 카테고리 (서비스 · 결제·환불 · 계정·로그인 · 기술·이용) / 10 항목.
 *
 * Compliance posture (자본시장법 §101 면제 트랙):
 *   - PivoxQuant 는 투자자문이나 매매 안내 서비스가 아니며 일반화된 정보를
 *     제공한다는 점을 명시.
 *   - 시그널 라벨(POSITIVE/NEGATIVE/NEUTRAL)은 특정 매매행동 지시가 아님.
 *   - 투자 권유 / 추천 / 조언 표현은 일절 사용하지 않음.
 *
 * v3 tone: hairline-ruled rows, Playfair UPRIGHT question, serif body.
 * Pure presentational — server-renderable.
 */

import * as React from "react";

interface FaqItem {
  q: string;
  a: React.ReactNode;
}

interface FaqGroup {
  category: string;
  items: FaqItem[];
}

const FAQ_GROUPS: FaqGroup[] = [
  {
    category: "서비스",
    items: [
      {
        q: "PivoxQuant는 어떤 서비스인가요?",
        a: (
          <>
            PivoxQuant는 미국·한국 주식에 대한 데이터와 퀀트·AI 기반 분석을
            일반화된 형태로 제공하는 정보 서비스입니다. 투자자문이나 매매 안내
            서비스가 아니며, 특정 종목의 매매를 권유하거나 개별 고객에게 맞춘
            조언을 제공하지 않습니다. 모든 화면의 정보는 참고용이며, 투자 판단과
            그 결과에 대한 책임은 이용자 본인에게 있습니다.
          </>
        ),
      },
      {
        q: "시그널 라벨(POSITIVE / NEGATIVE / NEUTRAL)은 무슨 뜻인가요?",
        a: (
          <>
            시그널 라벨은 여러 데이터 지표를 일반화해 요약한 관찰 결과입니다.
            특정 매매행동(매수·매도·보유 등)을 지시하거나 권유하는 신호가
            아닙니다. POSITIVE/NEGATIVE/NEUTRAL은 단지 분석 지표가 어느 방향으로
            관찰되었는지를 중립적으로 나타낼 뿐입니다.
          </>
        ),
      },
      {
        q: "데이터는 어디서 가져오나요?",
        a: (
          <>
            가격·재무·공시 데이터는 공식 라이선스를 보유한 출처(FMP,
            한국투자증권 API, SEC EDGAR, KRX/DART 공식 공개 데이터 등)에서만
            제공받습니다. 비공식 스크래핑 데이터는 사용하지 않습니다. 데이터는
            출처 사정에 따라 지연되거나 일시적으로 제공되지 않을 수 있습니다.
          </>
        ),
      },
    ],
  },
  {
    category: "결제·환불",
    items: [
      {
        q: "요금제는 어떻게 구성되어 있나요?",
        a: (
          <>
            무료(Free), Pro(월 ₩9,900), Premium(월 ₩19,900)의 3개 요금제가
            있습니다. 각 요금제에서 이용 가능한 기능은 요금 안내 페이지에서
            확인하실 수 있습니다.
          </>
        ),
      },
      {
        q: "결제·환불은 어떻게 처리되나요?",
        a: (
          <>
            결제·환불 관련 문의는 로그인 후 「1:1 문의하기」에서 결제·환불
            카테고리를 선택해 접수해 주세요. 처리 절차와 기한은 이용약관 및
            관련 법령(전자상거래법 등)에 따릅니다. 결제 내역과 문의 내용을 함께
            남겨 주시면 확인이 빠릅니다.
          </>
        ),
      },
    ],
  },
  {
    category: "계정·로그인",
    items: [
      {
        q: "로그인은 어떻게 하나요?",
        a: (
          <>
            Google 또는 Kakao 계정으로 로그인할 수 있습니다. 별도의
            이메일·비밀번호 가입은 제공하지 않습니다. 로그인이 되지 않을 경우
            사용 중인 브라우저를 최신 버전으로 업데이트하거나, 시크릿 모드를 해제한
            뒤 다시 시도해 보세요.
          </>
        ),
      },
      {
        q: "계정을 탈퇴하려면 어떻게 하나요?",
        a: (
          <>
            설정 화면에서 회원 탈퇴를 진행할 수 있습니다. 탈퇴 시 개인정보는
            개인정보처리방침 및 관련 법령(개인정보 보호법)에 따라 처리됩니다.
            진행 중 문제가 있으면 1:1 문의로 알려 주세요.
          </>
        ),
      },
    ],
  },
  {
    category: "기술·이용",
    items: [
      {
        q: "앱으로 설치할 수 있나요? (PWA)",
        a: (
          <>
            PivoxQuant는 PWA(Progressive Web App)로, 모바일·데스크톱 브라우저의
            「홈 화면에 추가」 또는 「설치」 기능으로 앱처럼 설치할 수 있습니다.
            설치하면 전체 화면으로 더 빠르게 이용할 수 있습니다.
          </>
        ),
      },
      {
        q: "데이터나 화면이 오래된 것 같아요.",
        a: (
          <>
            상단에 데이터 지연 안내 배너가 표시될 수 있습니다. 브라우저를
            새로고침하면 최신 데이터를 다시 불러옵니다. PWA로 설치한 경우 앱을
            완전히 종료한 뒤 다시 여는 것도 도움이 됩니다.
          </>
        ),
      },
      {
        q: "문의는 어떻게 하나요?",
        a: (
          <>
            로그인 후 「AI 고객지원에게 물어보기」로 결제·계정·사용법 질문을
            빠르게 해결하거나, 「1:1 문의하기」로 직접 문의를 접수할 수 있습니다.
            접수한 문의와 답변은 「내 문의함」에서 확인할 수 있습니다.
          </>
        ),
      },
    ],
  },
];

function FaqRow({ item }: { item: FaqItem }) {
  return (
    <details
      className="group pq-faq-item"
      style={{ borderTop: "0.5px solid var(--pq-ivory-line)" }}
    >
      <summary
        className="flex cursor-pointer list-none items-start justify-between gap-4 py-4"
        style={{ outline: "none" }}
      >
        <span
          className="font-display text-pq-h6"
          style={{
            color: "var(--pq-ivory)",
            lineHeight: 1.4,
            letterSpacing: "-0.01em",
            wordBreak: "keep-all",
          }}
        >
          {item.q}
        </span>
        <span
          aria-hidden="true"
          className="mt-1 shrink-0 text-lg leading-none transition-transform duration-200 group-open:rotate-45"
          style={{ color: "var(--pq-bronze)" }}
        >
          +
        </span>
      </summary>
      <p
        className="pb-4 font-serif text-pq-lead"
        style={{
          lineHeight: 1.7,
          color: "var(--pq-ivory-soft)",
          wordBreak: "keep-all",
        }}
      >
        {item.a}
      </p>
    </details>
  );
}

export function FaqSection() {
  return (
    <section aria-labelledby="faq-heading">
      <h2
        id="faq-heading"
        className="font-sans text-pq-eyebrow uppercase"
        style={{
          letterSpacing: "0.2em",
          color: "var(--pq-bronze)",
          fontWeight: 500,
        }}
      >
        자주 묻는 질문
      </h2>

      <div className="mt-4 space-y-8">
        {FAQ_GROUPS.map((group) => (
          <div key={group.category}>
            <h3
              className="font-display text-pq-h5"
              style={{
                color: "var(--pq-ivory)",
                letterSpacing: "-0.015em",
                marginBottom: 4,
              }}
            >
              {group.category}
            </h3>
            <div
              style={{ borderBottom: "0.5px solid var(--pq-ivory-line)" }}
            >
              {group.items.map((item) => (
                <FaqRow key={item.q} item={item} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
