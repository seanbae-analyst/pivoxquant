"use client";

/**
 * DoorwaySection — /settings · 「문 앞의 한 줄」 (2026-10-15).
 *
 * docs/design/doorway-pause_2026-10-15.md. 「멈춤」 works only when the user
 * remembers to open PivoxQuant before buying; the impulse starts when the
 * broker app opens. This section shows how to make the user's OWN phone ask
 * one question at that moment — "뭘 하러 왔어요?" (그냥 보기 / 살 게 있음 /
 * 팔 게 있음 + 한 줄) — and send the answer with the personal import token
 * they already use for 체결 자동 기록 (routes/doorway.py ``/webhook``).
 *
 * The webhook takes only tokens issued under the consent text that names
 * door answers (`doorway_ok`, 2026-10-15 — legal-kr-fintech review); older
 * tokens keep working for fills. KeyStatus says which active key qualifies.
 *
 *   - 아이폰: 단축어 '앱 → 열 때' 자동화 + '메뉴에서 선택' + 'URL 콘텐츠
 *     가져오기'. The menu branch's text is "보기" / "살 …" / "팔 …" and the
 *     server reads the head word (services/doorway/service.py::parse_text).
 *   - 안드로이드: MacroDroid '앱 실행' 트리거 + '웹 사이트 열기' → the web door
 *     (/pre-trade/door?app=…), answered in the browser; back returns to the
 *     broker app. No token needed there — the browser session is the user.
 *
 * Both phone paths are marked 시험 중: the steps follow the OS menus as
 * documented, but were not run on a device for every iOS / MacroDroid version.
 *
 * Nothing here touches a brokerage account or an order. The token can only
 * add fills to the pending list and leave door answers. Facts only.
 */
import * as React from "react";
import Link from "next/link";

import { API } from "@/lib/endpoints";
import { useImportTokens } from "@/lib/hooks";
import { Caption, EditorialHead, RuledKicker } from "@/components/ui/editorial";
import { CopyField } from "@/components/settings/import-tokens-section";

/** Broker apps the automation can tag its answer with (``app`` in the body). */
export const DOOR_APPS: ReadonlyArray<{ id: string; label: string }> = [
  { id: "toss", label: "토스증권" },
  { id: "kiwoom", label: "키움증권" },
  { id: "mirae", label: "미래에셋증권" },
  { id: "samsung", label: "삼성증권" },
  { id: "kis", label: "한국투자증권" },
  { id: "nh", label: "NH투자증권" },
  { id: "kb", label: "KB증권" },
  { id: "shinhan", label: "신한투자증권" },
  { id: "kakaopay", label: "카카오페이증권" },
  { id: "other", label: "그 밖의 앱" },
];

export function doorwayWebhookUrl(origin: string): string {
  return `${origin}${API.doorway.webhook}`;
}

/** The web door an Android automation (or anyone) opens. */
export function doorPageUrl(origin: string, app: string): string {
  return `${origin}/pre-trade/door?app=${encodeURIComponent(app)}`;
}

/** Body of the iOS "URL 콘텐츠 가져오기" — [메뉴 결과] is the menu's output. */
export function shortcutBody(app: string): string {
  return `{"text":"[메뉴 결과]","app":"${app}"}`;
}

const IOS_STEPS: ReadonlyArray<string> = [
  "1. 단축어 앱에서 + 를 눌러 새 단축어를 만들고, '편집' → '자동화' → '앱'을 고릅니다. 앱은 쓰는 증권 앱, '열 때'를 체크합니다. (iOS 26 이하: 아래 '자동화' 탭 → 새로운 자동화 → '앱'에서 같은 값을 고르고 '즉시 실행'을 고릅니다.)",
  "2. 동작 추가 → '메뉴에서 선택'. 질문에 '뭘 하러 왔어요?'를 넣고 항목을 세 개 만듭니다: 그냥 보기 · 살 게 있음 · 팔 게 있음.",
  "3. '그냥 보기' 아래에 동작 '텍스트'를 넣고 보기 라고 적습니다.",
  "4. '살 게 있음' 아래에 '텍스트'를 넣고 살 을 적은 뒤 한 칸 띄우고 변수 '매번 묻기'를 넣습니다 — 실행할 때 종목과 이유 한 줄을 묻습니다. '팔 게 있음' 아래도 같은 방식으로 팔 + '매번 묻기'.",
  "5. 메뉴가 끝난 아래에 'URL 콘텐츠 가져오기'. URL 에 위 '보낼 주소'를 넣고, 방법을 POST 로 바꾼 뒤 헤더를 추가합니다. 키 Authorization, 값에는 체결 자동 기록에서 쓰는 'Bearer …' 한 줄.",
  "6. 요청 본문은 JSON → 필드 두 개(텍스트). text 에는 변수 '메뉴 결과', app 에는 위에서 고른 앱 이름을 넣습니다.",
  "7. (선택) 그 아래에 '사전 값 가져오기'(키: message) → '알림 보기'를 넣으면 '기록했어요 · 오늘 3번째 열림' 같은 한 줄이 뜹니다.",
];

const ANDROID_STEPS: ReadonlyArray<string> = [
  "1. MacroDroid 에서 '매크로 추가'를 누릅니다.",
  "2. 트리거 → '애플리케이션' → '앱 실행/종료' → '실행 시'를 고르고, 쓰는 증권 앱을 고릅니다.",
  "3. 액션 → '웹 사이트 열기'(또는 'URL 열기')에 위 '문 주소'를 붙여 넣습니다.",
  "4. 저장합니다. 증권 앱을 열면 브라우저에 질문이 뜨고, 답한 뒤 뒤로 가기를 누르면 증권 앱으로 돌아갑니다. 브라우저에 PivoxQuant 로그인이 되어 있어야 합니다.",
];

/** Whether an active token may send door answers (issued after 2026-10-15). */
function KeyStatus() {
  const { tokens, isLoading } = useImportTokens();
  if (isLoading) return null;
  const usable = tokens.filter((t) => !t.revoked_at && t.doorway_ok);
  return (
    <p className="mt-1.5 text-[12.5px]" style={{ color: "var(--pq-ivory-dim)" }} data-testid="doorway-key-status">
      {usable.length > 0
        ? `문 앞 기록을 보낼 수 있는 열쇠: ${usable.map((t) => t.name).join(", ")}`
        : "아직 문 앞 기록을 보낼 수 있는 열쇠가 없어요."}
    </p>
  );
}

const cardStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.02)",
  border: "1px solid var(--pq-ivory-line)",
  borderRadius: "var(--pq-radius-card)",
  padding: 24,
};

export function DoorwaySection() {
  const [origin, setOrigin] = React.useState("");
  React.useEffect(() => {
    if (typeof window !== "undefined") setOrigin(window.location.origin);
  }, []);
  const [app, setApp] = React.useState("toss");

  return (
    <section
      id="doorway"
      style={{ scrollMarginTop: 96 }}
      aria-label="문 앞의 한 줄"
      data-testid="doorway-section"
    >
      {/* Phone: the settings back row names this section. */}
      <div className="hidden md:block" style={{ marginBottom: 16 }}>
        <EditorialHead size={30} as="div">
          문 앞의 한 줄
        </EditorialHead>
      </div>

      <div style={cardStyle}>
        <Caption className="max-w-xl">
          증권 앱을 열 때 폰이 &ldquo;뭘 하러 왔어요?&rdquo;를 한 번 묻습니다. 그냥 보기 · 살 게
          있음 · 팔 게 있음 중 하나를 고르고, 살 거나 팔 거라면 한 줄을 적습니다. 답은 거울의
          &lsquo;문 앞&rsquo;에 쌓이고, 그 뒤 체결과 나란히 보입니다.
        </Caption>
        <Caption className="mt-2 max-w-xl">
          증권사 계정이나 주문에는 닿지 않습니다. 폰이 보내는 것은 고른 답, 적은 한 줄, 앱 이름,
          보낸 시각뿐입니다. 남은 기록은 웹 문 화면 아래 목록에서 하나씩 지울 수 있습니다.
        </Caption>

        <div className="mt-5">
          <RuledKicker>준비물</RuledKicker>
          <Caption className="mt-2 max-w-xl">
            아이폰은{" "}
            <Link
              href="/settings?s=import"
              className="underline underline-offset-2"
              style={{ color: "var(--pq-bronze)" }}
            >
              체결 자동 기록
            </Link>
            에서 연결 열쇠(가져오기 토큰)를 새로 만들어 씁니다. 문 앞 기록 동의 문구가 생기기
            전에 만든 열쇠는 쓸 수 없어요 — 체결 자동 기록에는 그대로 써도 됩니다. 안드로이드는
            열쇠 없이 브라우저 로그인으로 됩니다.
          </Caption>
          <KeyStatus />
        </div>

        <div className="mt-5">
          <label className="block">
            <span className="text-[12.5px]" style={{ color: "var(--pq-ivory-dim)" }}>
              어느 증권 앱에 붙이나요
            </span>
            <select
              value={app}
              onChange={(e) => setApp(e.target.value)}
              className="mt-1 block w-full max-w-xs rounded-[var(--pq-radius-cta)] border bg-transparent px-3 py-2 text-[14px]"
              style={{ borderColor: "var(--pq-ivory-line)", color: "var(--pq-ivory)" }}
              data-testid="doorway-app"
            >
              {DOOR_APPS.map((a) => (
                <option key={a.id} value={a.id} style={{ background: "rgb(5,5,5)" }}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <details
          className="mt-5 rounded-[var(--pq-radius-card)] border p-4"
          style={{ borderColor: "var(--pq-ivory-line)", background: "rgba(0,0,0,0.2)" }}
          data-testid="doorway-ios"
        >
          <summary className="cursor-pointer text-[14px]" style={{ color: "var(--pq-bronze)" }}>
            아이폰 · 단축어 (시험 중)
          </summary>
          <CopyField label="보낼 주소 (URL)" value={doorwayWebhookUrl(origin)} testId="doorway-url" />
          <CopyField label="본문 (JSON)" value={shortcutBody(app)} testId="doorway-body" />
          <ol className="mt-4 space-y-1.5">
            {IOS_STEPS.map((s) => (
              <li key={s}>
                <Caption>{s}</Caption>
              </li>
            ))}
          </ol>
        </details>

        <details
          className="mt-3 rounded-[var(--pq-radius-card)] border p-4"
          style={{ borderColor: "var(--pq-ivory-line)", background: "rgba(0,0,0,0.2)" }}
          data-testid="doorway-android"
        >
          <summary className="cursor-pointer text-[14px]" style={{ color: "var(--pq-bronze)" }}>
            안드로이드 · MacroDroid (시험 중)
          </summary>
          <CopyField label="문 주소" value={doorPageUrl(origin, app)} testId="doorway-door-url" />
          <ol className="mt-4 space-y-1.5">
            {ANDROID_STEPS.map((s) => (
              <li key={s}>
                <Caption>{s}</Caption>
              </li>
            ))}
          </ol>
        </details>

        <div className="mt-5">
          <RuledKicker>잘 되는지 확인</RuledKicker>
          <Caption className="mt-2 max-w-xl">
            증권 앱을 한 번 열어 답해 보세요. 거울의 &lsquo;문 앞&rsquo;에 열린 횟수가 올라갑니다.
            폰 없이 화면만 보려면{" "}
            <Link
              href={`/pre-trade/door?app=${encodeURIComponent(app)}`}
              className="underline underline-offset-2"
              style={{ color: "var(--pq-bronze)" }}
            >
              웹 문 열어 보기
            </Link>
            .
          </Caption>
          <Caption className="mt-2 max-w-xl">
            매번 뜨는 게 번거로우면 단축어·MacroDroid 에서 자동화를 잠시 끄면 됩니다.
          </Caption>
        </div>
      </div>
    </section>
  );
}

export default DoorwaySection;
