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

/** True when launched from the home-screen icon (Android standalone or iOS). */
export function isStandaloneDisplay(): boolean {
  if (typeof window === "undefined") return false;
  if (window.matchMedia?.("(display-mode: standalone)").matches) return true;
  return Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone);
}

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

  if (seen !== false) return <div className="min-h-[100dvh]" style={{ background: "var(--pq-ink)" }} />;

  const last = index >= CARDS.length - 1;

  return (
    <div
      className="flex min-h-[100dvh] flex-col text-[var(--pq-ivory)]"
      style={{
        background: "var(--pq-ink)",
        paddingTop: "env(safe-area-inset-top, 0px)",
        paddingBottom: "env(safe-area-inset-bottom, 0px)",
      }}
      data-testid="app-welcome"
    >
      <div className="flex items-center justify-between px-6 pt-5">
        <span className="font-serif text-[17px]">PivoxQuant</span>
        {!last && (
          <button
            type="button"
            onClick={() => goTo(CARDS.length - 1)}
            className="min-h-[44px] px-2 text-[14px] text-[var(--pq-ivory-dim)]"
          >
            건너뛰기
          </button>
        )}
      </div>

      <div
        ref={track}
        onScroll={onScroll}
        className="flex flex-1 snap-x snap-mandatory overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        data-testid="app-welcome-track"
      >
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

      <div className="px-6 pb-6">
        <div className="mb-6 flex justify-center gap-2" aria-hidden>
          {CARDS.map((c, i) => (
            <span
              key={c.kicker}
              className="h-[6px] rounded-full transition-all"
              style={{
                width: i === index ? 18 : 6,
                background: i === index ? "var(--pq-bronze)" : "var(--pq-ivory-line)",
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
