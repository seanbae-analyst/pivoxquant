import { toast } from "sonner";
import { hadSession } from "./had-session";
import { isDemoMode, demoResponseFor } from "./demo";

/** Default request timeout in milliseconds. */
const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * Read the CSRF token from the csrf_token cookie.
 * The backend sets this cookie on every response (httpOnly=false).
 */
function getCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith("csrf_token="));
  return match ? decodeURIComponent(match.split("=")[1]) : undefined;
}

/**
 * Read the active locale from the sp_locale cookie. Falls back to "ko".
 * Mirrors the LocaleProvider in lib/locale.tsx — kept in sync so backend
 * error_kr / error responses can be surfaced in the user's chosen language.
 */
function getLocale(): "ko" | "en" {
  if (typeof document === "undefined") return "ko";
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith("sp_locale="));
  const value = match ? decodeURIComponent(match.split("=")[1]) : "ko";
  return value === "en" ? "en" : "ko";
}

/**
 * Backend `api_error(en=..., kr=...)` returns both `error` (en) and
 * `error_kr` (ko). Pick the locale-appropriate one with safe fallbacks.
 */
function pickErrorMessage(
  body: Record<string, unknown> | undefined,
  fallback: string,
): string {
  if (!body) return fallback;
  const locale = getLocale();
  if (locale === "ko" && typeof body.error_kr === "string" && body.error_kr) {
    return body.error_kr;
  }
  if (typeof body.error === "string" && body.error) return body.error;
  if (typeof body.error_kr === "string" && body.error_kr) return body.error_kr;
  return fallback;
}

export interface ApiFetchOptions extends RequestInit {
  /** Override the default 30s timeout. Pass 0 to disable. */
  timeoutMs?: number;
}

/**
 * One retry when the FIRST attempt times out on a read.
 *
 * The backend runs on Render's free plan, which spins the service down after
 * 15 idle minutes. Measured 2026-09-07 against production:
 *
 *   cold  /api/health → 43.9 s
 *   warm  /api/health →  0.52 s (three consecutive samples, ±0.02)
 *
 * DEFAULT_TIMEOUT_MS is 30 s, which sits BETWEEN those two numbers. So every
 * visitor arriving after an idle gap — on a closed beta with almost no
 * traffic, that is most visitors — had their first request aborted at 30 s
 * and saw ApiError(408). The service was not down; it was still booting.
 *
 * Raising the blanket timeout past 44 s would make every genuine failure hang
 * for 44 s too. Retrying is better here because of what the first attempt
 * does: it is the request that WAKES the service. By the time it is aborted
 * the container is nearly up, so the retry lands on a warm server and returns
 * in well under a second.
 *
 * Deliberately narrow:
 *   - Only on OUR timeout. A caller-aborted request (route change, component
 *     unmount, an explicit AbortController) throws as before and is never
 *     retried.
 *   - Only ONCE. A second timeout means something other than a cold start.
 *   - Only for idempotent methods. Replaying a POST could double-create a
 *     pre-trade record or a trade; a request that timed out may still have
 *     been received and applied by the server.
 *   - Only when the caller did not set its own timeoutMs — an explicit budget
 *     is a decision we should not silently double.
 *
 * The real fix is for the service not to be asleep. Until then this keeps a
 * cold start from reading as an outage.
 */
const IDEMPOTENT_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export async function apiFetch<T = unknown>(
  path: string,
  init?: ApiFetchOptions,
): Promise<T> {
  try {
    return await apiFetchOnce<T>(path, init);
  } catch (err) {
    const method = (init?.method ?? "GET").toUpperCase();
    const isOurTimeout = err instanceof ApiError && err.status === 408;
    const retryable =
      isOurTimeout &&
      IDEMPOTENT_METHODS.has(method) &&
      init?.timeoutMs === undefined &&
      !init?.signal?.aborted;
    if (!retryable) throw err;
    return await apiFetchOnce<T>(path, init);
  }
}


async function apiFetchOnce<T = unknown>(
  path: string,
  init?: ApiFetchOptions,
): Promise<T> {
  // DEMO mode (portfolio showcase): never touch a backend — resolve from canned
  // data. Additive + flag-gated; a no-op when NEXT_PUBLIC_DEMO_MODE is unset.
  if (isDemoMode()) {
    const demo = demoResponseFor(path, init?.method);
    if (demo.hit) return demo.body as T;
  }

  const csrfToken = getCsrfToken();
  const extra = init?.headers
    ? (init.headers instanceof Headers
      ? Object.fromEntries(init.headers.entries())
      : init.headers as Record<string, string>)
    : {};
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extra,
    ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
  };

  // Timeout via AbortController. Compose with any caller-supplied signal so
  // that aborting either source cancels the request.
  const timeoutMs = init?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const callerSignal = init?.signal;
  const onCallerAbort = () => controller.abort(callerSignal?.reason);
  if (callerSignal) {
    if (callerSignal.aborted) controller.abort(callerSignal.reason);
    else callerSignal.addEventListener("abort", onCallerAbort, { once: true });
  }
  const timeoutId = timeoutMs > 0
    ? setTimeout(() => controller.abort(new DOMException("Request timeout", "TimeoutError")), timeoutMs)
    : null;

  // Strip our custom field before forwarding to fetch.
  const { timeoutMs: _omit, signal: _omitSignal, headers: _omitHeaders, ...restInit } = init ?? {};
  void _omit; void _omitSignal; void _omitHeaders;

  let res: Response;
  try {
    res = await fetch(path, {
      credentials: "include",
      headers,
      ...restInit,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && (err.name === "AbortError" || err.name === "TimeoutError")) {
      // Distinguish caller-cancellation from our own timeout.
      if (callerSignal?.aborted) throw err;
      throw new ApiError(408, "Request timeout");
    }
    throw err;
  } finally {
    if (timeoutId !== null) clearTimeout(timeoutId);
    if (callerSignal) callerSignal.removeEventListener("abort", onCallerAbort);
  }

  // Handle session expiration — redirect to login.
  //
  // The backend emits `code: "SESSION_EXPIRED"` for any unauthenticated
  // request under @api_auth, including from devices that never logged in
  // (e.g. a first-time guest poking a protected endpoint). For those guests
  // the "세션이 만료" banner on /login?expired=1 is misleading — they were
  // never authenticated to begin with. We disambiguate by consulting the
  // `pq_had_session` localStorage flag set by AuthProvider on successful
  // session restore: only redirect with `?expired=1` if the user previously
  // held a session on this device. Otherwise drop the query string so the
  // /login page renders without the expiry banner.
  if (res.status === 401) {
    const body = await res.json().catch(() => ({}));
    if (body.code === "SESSION_EXPIRED" && typeof window !== "undefined") {
      const target = hadSession() ? "/login?expired=1" : "/login";
      window.location.href = target;
      throw new ApiError(401, pickErrorMessage(body, "Session expired"));
    }
    throw new ApiError(401, pickErrorMessage(body, res.statusText));
  }

  // Handle rate limiting — surface to user via toast (locale-aware).
  if (res.status === 429) {
    const retryAfter = res.headers.get("Retry-After") || "60";
    if (typeof window !== "undefined") {
      const msg = getLocale() === "ko"
        ? `너무 많은 요청. ${retryAfter}초 후 다시 시도해주세요.`
        : `Too many requests. Please try again in ${retryAfter}s.`;
      toast.error(msg);
    }
    throw new ApiError(429, "Rate limit exceeded");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, pickErrorMessage(body, res.statusText));
  }
  return res.json();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
