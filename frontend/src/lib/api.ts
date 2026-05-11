import { toast } from "sonner";
import { hadSession } from "./had-session";

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

export interface ApiFetchOptions extends RequestInit {
  /** Override the default 30s timeout. Pass 0 to disable. */
  timeoutMs?: number;
}

export async function apiFetch<T = unknown>(
  path: string,
  init?: ApiFetchOptions,
): Promise<T> {
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
      throw new ApiError(401, body.error ?? "Session expired");
    }
    throw new ApiError(401, body.error ?? res.statusText);
  }

  // Handle rate limiting — surface to user via toast
  if (res.status === 429) {
    const retryAfter = res.headers.get("Retry-After") || "60";
    if (typeof window !== "undefined") {
      toast.error(`너무 많은 요청. ${retryAfter}초 후 다시 시도해주세요.`);
    }
    throw new ApiError(429, "Rate limit exceeded");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.error ?? res.statusText);
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
