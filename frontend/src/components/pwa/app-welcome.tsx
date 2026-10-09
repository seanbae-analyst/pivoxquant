"use client";

/**
 * AppWelcome — the first screen of the INSTALLED app for a signed-out user.
 *
 * 2026-10-07, CEO: "랜딩페이지라는 개념이 앱에는 없잖아". A browser visitor
 * still gets the marketing landing (it is how the beta is passed around and
 * how people learn to install). Someone who opened the home-screen icon has
 * already decided; they get three cards and a start button, once. After the
 * cards have been seen, the icon opens straight to /login.
 *
 * Copy is the loop the app actually ships — the same three screens as
 * landing/three-steps.tsx. Do not add a claim a route does not do.
 *
 * Swipe is plain CSS scroll-snap: no gesture library, works with the
 * reduced-motion setting, and the dots follow the scroll position.
 */

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AppCover } from "./app-cover";

// AppCover / isStandaloneDisplay live in ./app-cover so "/" can paint the
// cover without pulling this module (the welcome cards) into its first chunk.
export { AppCover, isStandaloneDisplay } from "./app-cover";

export const WELCOME_SEEN_KEY = "pq_app_welcome_seen";

const CARDS: ReadonlyArray<{ kicker: string; title: string; body: string }> = [
  {
    kicker: "멈춤",
    title: "사기 전에, 멈춰서 이유를 적습니다.",
    body: "주문 전에 일곱 개의 질문에 답합니다. 종목을 골라 주지 않습니다.",
  },
  {
    kicker: "기록",
    title: "체결이 들어오면, 한 줄 남깁니다.",
    body: "폰으로 받은 체결 알림이 기록 대기함에 올라옵니다. 잊기 전에 왜 했는지 적습니다.",
  },
  {
    kicker: "거울",
    title: "말한 나와 실제의 나를 나란히 봅니다.",
    body: "가입 때 답한 투자 습관과 최근 30일 매매를 비교합니다. 점수는 매기지 않습니다.",
  },
];

function readSeen(): boolean {
  try {
    return window.localStorage.getItem(WELCOME_SEEN_KEY) === "1";
  } catch {
    return false;
  }
}

function markSeen() {
  try {
    window.localStorage.setItem(WELCOME_SEEN_KEY, "1");
  } catch {
    /* private mode — the cards simply show again next time */
  }
}

const noopSubscribe = () => () => {};

export function AppWelcome() {
  const router = useRouter();
  const track = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  // null on the server (unknown) — render nothing until the client knows.
  const seen = useSyncExternalStore<boolean | null>(noopSubscribe, readSeen, () => null);

  useEffect(() => {
    if (seen) router.replace("/login");
  }, [seen, router]);

  const onScroll = () => {
    const el = track.current;
    if (!el || el.clientWidth === 0) return;
    setIndex(Math.round(el.scrollLeft / el.clientWidth));
  };

  const goTo = (i: number) => {
    const el = track.current;
    if (!el) return;
    el.scrollTo({ left: i * el.clientWidth, behavior: "smooth" });
  };

  // Unknown, or already seen (→ /login): hold the cover, the picture the app opened on.
  if (seen !== false) return <AppCover />;

  // Slide 0 is the cover; slides 1..N are the cards.
  const slides = CARDS.length + 1;
  const onCover = index === 0;
  const last = index >= slides - 1;

  // Chrome (top bar, dots, buttons) stays off the cover so it reads like the
  // landing's first page; it fades in from the first card on.
  const chrome = `transition-opacity duration-300 ${onCover ? "pointer-events-none opacity-0" : "opacity-100"}`;

  return (
    <div
      className="relative min-h-[100dvh] text-[var(--pq-ivory)]"
      style={{ background: "var(--pq-ink)" }}
      // The whole welcome is app chrome (cover, three cards, buttons):
      // a long-press selects nothing, as on a native onboarding.
      data-pq-chrome
      data-testid="app-welcome"
    >
      <div
        ref={track}
        onScroll={onScroll}
        className="absolute inset-0 flex snap-x snap-mandatory overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        data-testid="app-welcome-track"
      >
        <section
          className="w-full shrink-0 snap-center"
          aria-label="PivoxQuant"
          onClick={() => goTo(1)}
        >
          <AppCover hint="넘겨 보세요  →" />
        </section>
        {CARDS.map((c, i) => (
          <section
            key={c.kicker}
            className="flex w-full shrink-0 snap-center flex-col justify-center px-8"
            aria-label={`${i + 1} / ${CARDS.length}`}
            data-testid="app-welcome-card"
          >
            <div className="text-[13px] tracking-[0.2em] text-[var(--pq-bronze)]">
              {String(i + 1).padStart(2, "0")} · {c.kicker}
            </div>
            <h1 className="mt-4 font-serif text-[30px] leading-[1.3] [word-break:keep-all]">
              {c.title}
            </h1>
            <p className="mt-4 text-[15px] leading-[1.6] text-[var(--pq-ivory-mid)] [word-break:keep-all]">
              {c.body}
            </p>
          </section>
        ))}
      </div>

      <div
        className={`absolute left-0 right-0 top-0 flex items-center justify-between px-6 pt-5 ${chrome}`}
        style={{ paddingTop: "calc(env(safe-area-inset-top, 0px) + 20px)" }}
        aria-hidden={onCover}
      >
        <span className="font-serif text-[17px]">PivoxQuant</span>
        {!last && (
          <button
            type="button"
            onClick={() => goTo(slides - 1)}
            tabIndex={onCover ? -1 : 0}
            className="min-h-[44px] px-2 text-[14px] text-[var(--pq-ivory-dim)]"
          >
            건너뛰기
          </button>
        )}
      </div>

      <div
        className={`absolute bottom-0 left-0 right-0 px-6 ${chrome}`}
        style={{ paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 24px)" }}
        aria-hidden={onCover}
      >
        <div className="mb-6 flex justify-center gap-2" aria-hidden>
          {CARDS.map((c, i) => (
            <span
              key={c.kicker}
              className="h-[6px] rounded-full transition-all"
              style={{
                width: i + 1 === index ? 18 : 6,
                background: i + 1 === index ? "var(--pq-bronze)" : "var(--pq-ivory-line)",
              }}
            />
          ))}
        </div>

        {last ? (
          <div className="flex flex-col gap-3">
            <Link
              href="/signup"
              onClick={markSeen}
              className="pq-ink-btn-bronze flex min-h-[52px] items-center justify-center text-[16px]"
              data-testid="app-welcome-start"
            >
              시작하기
            </Link>
            <Link
              href="/login"
              onClick={markSeen}
              className="flex min-h-[44px] items-center justify-center text-[15px] text-[var(--pq-ivory-dim)]"
            >
              이미 계정이 있어요 · 로그인
            </Link>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => goTo(index + 1)}
            tabIndex={onCover ? -1 : 0}
            className="pq-ink-btn-bronze flex min-h-[52px] w-full items-center justify-center text-[16px]"
            data-testid="app-welcome-next"
          >
            다음
          </button>
        )}
      </div>
    </div>
  );
}
