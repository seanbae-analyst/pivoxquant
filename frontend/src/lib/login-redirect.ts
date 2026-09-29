/**
 * 로그인 후 딥링크 (2026-09-29).
 *
 * 백엔드 OAuth 시작 경로(`API.auth.google` / `API.auth.kakao`)는 `?next=` 를
 * 받아 서명된 state 에 싣고, 로그인이 끝나면 그리로 보낸다
 * (routes/auth.py::_safe_next — 서버가 한 번 더 거른다). 이 모듈은 그 앞단:
 *   - 비로그인 유저를 /login 으로 보낼 때 원래 경로+쿼리를 `?next=` 로 싣고
 *   - 로그인 화면이 그 값을 걸러 OAuth 앵커 href 에 붙인다.
 */
import { safeNext } from "./safe-next";

/** /login 자신(과 같은 화면인 /signup·그 인터스티셜)으로의 next 는 루프다. */
const AUTH_ENTRY_PREFIXES = ["/login", "/signup"] as const;

/**
 * `raw` 가 로그인 뒤 돌아갈 만한 같은 출처 상대 경로면 그대로, 아니면 null.
 * "/" 로 시작하되 "//"·"/\\" 가 아니고, 스킴(`://`)이 없고, 로그인 화면 자신이
 * 아니어야 한다. 루트("/")는 돌아갈 곳이 아니므로 null (기본 착지 /mirror).
 */
export function loginNextPath(raw: string | null | undefined): string | null {
  if (typeof raw !== "string") return null;
  const v = raw.trim();
  if (!v || safeNext(v, "") !== v) return null;
  // 백엔드 _safe_next 도 "://" 가 어디든 있으면 버린다 — 같은 규칙.
  if (v.includes("://")) return null;
  const path = v.split(/[?#]/, 1)[0].replace(/\/+$/, "");
  if (path === "") return null;
  for (const p of AUTH_ENTRY_PREFIXES) {
    if (path === p || path.startsWith(p + "/")) return null;
  }
  return v;
}

/** 지금 창의 경로+쿼리 (SSR 에서는 null). */
export function currentLocationPath(): string | null {
  if (typeof window === "undefined") return null;
  return `${window.location.pathname}${window.location.search}`;
}

/** `/login` URL — `expired` 배너 플래그와 안전한 `next` 를 싣는다. */
export function loginHref(
  next: string | null | undefined,
  opts: { expired?: boolean } = {},
): string {
  const params = new URLSearchParams();
  if (opts.expired) params.set("expired", "1");
  const safe = loginNextPath(next);
  if (safe) params.set("next", safe);
  const qs = params.toString();
  return qs ? `/login?${qs}` : "/login";
}

/** OAuth 시작 경로에 안전한 `next` 를 붙인다 (없으면 그대로). */
export function oauthHref(base: string, next: string | null | undefined): string {
  const safe = loginNextPath(next);
  if (!safe) return base;
  const sep = base.includes("?") ? "&" : "?";
  return `${base}${sep}next=${encodeURIComponent(safe)}`;
}
