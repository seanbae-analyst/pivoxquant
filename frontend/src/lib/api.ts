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

export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const csrfToken = getCsrfToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
    ...(init?.headers as Record<string, string>),
  };

  const res = await fetch(path, {
    credentials: "include",
    headers,
    ...init,
  });

  // Handle session expiration — redirect to login
  if (res.status === 401) {
    const body = await res.json().catch(() => ({}));
    if (body.code === "SESSION_EXPIRED" && typeof window !== "undefined") {
      window.location.href = "/login?expired=1";
      throw new ApiError(401, body.error ?? "Session expired");
    }
    throw new ApiError(401, body.error ?? res.statusText);
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
