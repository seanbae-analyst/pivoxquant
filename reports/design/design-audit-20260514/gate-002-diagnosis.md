# GATE-002 베타게이트 우회 진단

**조사일**: 2026-05-14  
**조사자**: Investigator (READ-ONLY)  
**브랜치**: fix/design-audit-20260514

---

## 판정: **부분버그 (Partial Bug)**

루트 `/` 경로는 middleware matcher에 매칭되고, `BETA_BYPASS_PREFIXES`에도 포함되지 않으며, 의도적 제외 주석도 없다. 베타게이트가 동작해야 하는 경로임에도 랜딩이 노출되는 원인은 middleware 설계 문제가 아니라 **환경변수 `BETA_PASSWORD`가 설정되지 않은 상태에서 실행 중**일 가능성 또는 **`BETA_SIGNING_SECRET`이 없어 `expected = null`이 되는 코드 경로** 때문이다 (아래 상세 설명 참조).

---

## 베타게이트 메커니즘 요약

### 1. middleware.ts 위치
- `/Users/seanbae/Desktop/취준/pivoxquant/frontend/middleware.ts` (frontend 루트, src/ 아래 아님)

### 2. matcher
```
/((?!api|_next/static|_next/image|favicon.ico|icons|videos|sw.js|offline.html|logo|agents-preview).*)
```
- 루트 `/`는 이 패턴에 **매칭됨** (node 실행 결과로 확인: `/ -> true`)
- `/beta-gate`, `/home`, `/login`, `/simulator`, `/pricing` 모두 매칭됨

### 3. 베타게이트 bypass 목록 (`BETA_BYPASS_PREFIXES`, middleware.ts:46-56)
```ts
const BETA_BYPASS_PREFIXES = [
  "/beta-gate",       // 게이트 페이지 자체
  "/api/beta-auth",   // 인증 API
  "/manifest",
  "/sw.js",
  "/offline.html",
  "/robots.txt",
  "/sitemap.xml",
  "/simulator",       // 주석: "Public viral page — accessible without beta password (acquisition funnel)"
];
```
루트 `/`는 이 목록에 **없음**. 의도적 제외 주석 **없음**.

### 4. 게이트 체크 로직 (middleware.ts:106-133)
```ts
if (BETA_PASSWORD && !isBetaBypass(pathname) && !isCrawler) {
  const token = request.cookies.get(BETA_COOKIE_NAME)?.value;
  const expected = BETA_SIGNING_SECRET ? await betaSignedToken() : null;
  if (!expected || token !== expected) {
    // → /beta-gate 로 redirect
  }
}
```

**버그 경로 A**: `BETA_PASSWORD` env가 falsy이면 조건문 전체가 스킵된다.  
`// No password env → skipped entirely so local dev stays unblocked.` (middleware.ts:102-103)  
프로덕션에서 `BETA_PASSWORD`가 Vercel 환경변수로 설정되어 있지 않거나 비어있으면 모든 경로가 게이트 없이 통과한다.

**버그 경로 B**: `BETA_SIGNING_SECRET`(및 `SECRET_KEY`)가 falsy이면 `expected = null`이 되어 `!expected`가 true → redirect 발생. 이 경우는 게이트가 작동하는 것처럼 보이나 `/beta-gate` 자체만 접근 가능한 무한루프 상태가 된다.

### 5. 저장 방식
- Cookie 이름: `pivox_beta_access`
- Cookie 속성: `httpOnly: true`, `secure: production`, `sameSite: lax`, `maxAge: 30일`
- 토큰 형식: `v2.<HMAC-SHA256(BETA_SIGNING_SECRET, "v2:beta-verified")>`
- 발급 경로: `POST /api/beta-auth` → route.ts에서 `timingSafeEqual`로 비밀번호 검증 후 Set-Cookie

---

## 루트 `/` 우회 상세 진단

| 항목 | 확인 결과 |
|------|-----------|
| middleware matcher에 `/` 포함 | **포함됨** (node 실행 확인) |
| `BETA_BYPASS_PREFIXES`에 `/` 포함 | **미포함** |
| 의도적 제외 주석 | **없음** |
| 랜딩 "공개 마케팅" 명시 주석 | **없음** (`page.tsx` 전체 확인) |
| `/simulator`는 명시적 공개 | **있음** — 주석 "Public viral page — accessible without beta password (acquisition funnel)" |
| middleware 게이트 스킵 조건 | `BETA_PASSWORD` falsy 시 전체 스킵 |

**결론**: `/`에 베타게이트가 적용되도록 설계되었으나, `BETA_PASSWORD` 환경변수가 없으면 전체 게이트가 비활성화된다. 설계는 올바르나 환경변수 누락 또는 Vercel 배포 시 env 미주입이 우회의 실제 원인일 가능성이 높다.

---

## `(dashboard)` 앱 페이지 보호 상태

`(dashboard)/layout.tsx:81-83` (확인됨):
```ts
useEffect(() => {
  if (!loading && !user) {
    router.replace("/login");
  }
```
`layout.tsx:116-118`:
```ts
if (!user) {
  return null;
}
```

- 베타게이트(middleware) + OAuth 인증(layout useAuth) **2중 보호** 구조
- 베타게이트가 뚫려도 대시보드 페이지는 미인증 시 `/login`으로 redirect
- verify-ux 결과 "앱 페이지는 /login redirect"는 **정확** — 인증 레이어가 독립적으로 작동 중

---

## Cookie 위조 가능성

- `httpOnly: true` → JavaScript로 쿠키 읽기/쓰기 불가. XSS로 탈취 불가.
- 토큰 = `v2.<HMAC-SHA256(secret, "v2:beta-verified")>`. `BETA_SIGNING_SECRET`(또는 `SECRET_KEY`) 없이 유효 토큰 생성 불가.
- `BETA_SIGNING_SECRET`가 노출되지 않으면 위조 불가.
- `secure: true`(production) → HTTPS 전용, 평문 HTTP intercept 불가.

**판정**: 위조 가능성은 `BETA_SIGNING_SECRET`이 유출된 경우에만 해당. 현재 설계는 보안상 적절.

---

## 만약 실제 버그 fix가 필요하다면 (READ-ONLY 보고 — fix 범위 외)

**1. 환경변수 확인 (fix 아님, 확인 요청)**  
Vercel Dashboard → pivoxquant → Settings → Environment Variables에서 `BETA_PASSWORD`와 `BETA_SIGNING_SECRET`이 Production 환경에 설정되어 있는지 확인.

**2. 만약 env는 맞는데 `/`에서 landing이 그대로 노출된다면** → middleware가 edge runtime에서 `BETA_PASSWORD`를 못 읽는 케이스. 이 경우:  
- `frontend/middleware.ts:10` `const BETA_PASSWORD = process.env.BETA_PASSWORD;` 값이 undefined인지 Vercel 함수 로그에서 확인 필요.

**3. `/`를 `BETA_BYPASS_PREFIXES`에 추가하는 것은 버그 fix가 아님** — 오히려 게이트를 제거하는 것. 이 목록에서 제외가 맞음.

---

## 잔존/누락 사항

- `BETA_PASSWORD` Vercel env 실제 설정 여부를 이 조사에서 확인 불가 (env 파일 접근 불가). CEO가 Vercel 콘솔에서 직접 확인 필요.
- `frontend/middleware.ts`는 `frontend/src/` 안이 아닌 `frontend/` 루트에 위치 — Next.js App Router 규격상 이 위치가 맞음.
- BETA_TOKEN_VERSION `v2`가 `middleware.ts:19`와 `api/beta-auth/route.ts:8` 양쪽에 하드코딩 — 불일치 위험 있음 (공유 상수 없음). 이건 이 조사 범위 외.

---

## 검증 증거

| 파일 | 라인 | 내용 |
|------|------|------|
| `frontend/middleware.ts` | 102-103 | `// No password env → skipped entirely so local dev stays unblocked.` |
| `frontend/middleware.ts` | 106 | `if (BETA_PASSWORD && !isBetaBypass(pathname) && !isCrawler)` |
| `frontend/middleware.ts` | 46-56 | `BETA_BYPASS_PREFIXES` — `/` 없음 |
| `frontend/middleware.ts` | 231 | matcher regex — `/` 매칭됨 (node 실행 확인) |
| `frontend/src/app/(dashboard)/layout.tsx` | 81-83, 116-118 | 미인증 시 `/login` redirect + `return null` |
| `frontend/src/app/page.tsx` | 64-73 | 미인증이면 `<LandingV2 />` 렌더 (middleware 통과 후) |
| git log | `1272e9e0` | `/simulator`만 명시적 "acquisition funnel" 공개 처리 — `/`는 해당 없음 |
