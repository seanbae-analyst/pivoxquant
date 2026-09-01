# 야간 빌드 검증 — 2026-09-01 03:00 KST

브랜치: `main`
HEAD: `375c633a docs: bring CLAUDE.md back in line with the deployed tree (#543)`
미커밋: 1개 · untracked: 1개

## 1. 앱 부팅
- ✅ OK routes=135

## 2. 백엔드 테스트
```
    assert Artifact.query.get(art_id).opened_at is None

tests/test_sendgrid_webhook.py::test_signature_required_when_env_absent
  /Users/seanbae/Desktop/취준/pivoxquant/tests/test_sendgrid_webhook.py:470: LegacyAPIWarning: The Query.get() method is considered legacy as of the 1.x series of SQLAlchemy and becomes a legacy construct in 2.0. The method is now available as Session.get() (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    assert Artifact.query.get(art_id).opened_at is None

tests/test_sendgrid_webhook.py::test_valid_signature_accepted
  /Users/seanbae/Desktop/취준/pivoxquant/tests/test_sendgrid_webhook.py:514: LegacyAPIWarning: The Query.get() method is considered legacy as of the 1.x series of SQLAlchemy and becomes a legacy construct in 2.0. The method is now available as Session.get() (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    assert Artifact.query.get(art_id).opened_at is not None

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
==== 2235 passed, 18 skipped, 1 xfailed, 520 warnings in 980.98s (0:16:20) =====
```

## 3. 프론트엔드
- node: `/Users/seanbae/.nvm/versions/node/v20.20.2/bin` (v20.20.2)

### tsc — ✅ exit 0
```
```
### vitest — ✅ exit 0
```
 [32m✓[39m src/components/portfolio/__tests__/to-position.test.ts [2m([22m[2m5 tests[22m[2m)[22m[32m 28[2mms[22m[39m
 [32m✓[39m src/__tests__/nav-dropdown-singleton.test.tsx [2m([22m[2m6 tests[22m[2m)[22m[32m 70[2mms[22m[39m
 [32m✓[39m src/data/__tests__/onboarding-slider-seedable.test.ts [2m([22m[2m1 test[22m[2m)[22m[32m 18[2mms[22m[39m
 [32m✓[39m src/__tests__/dashboard-redirect.test.ts [2m([22m[2m4 tests[22m[2m)[22m[32m 9[2mms[22m[39m
 [32m✓[39m src/app/(dashboard)/__tests__/auth-redirect.test.ts [2m([22m[2m6 tests[22m[2m)[22m[32m 6[2mms[22m[39m
 [32m✓[39m src/lib/cfo/__tests__/coerce-pulse.test.ts [2m([22m[2m3 tests[22m[2m)[22m[32m 8[2mms[22m[39m

[2m Test Files [22m [1m[32m47 passed[39m[22m[90m (47)[39m
[2m      Tests [22m [1m[32m353 passed[39m[22m[90m (353)[39m
[2m   Start at [22m 03:17:16
[2m   Duration [22m 61.09s[2m (transform 9.79s, setup 16.15s, import 61.47s, tests 91.10s, environment 205.49s)[22m

```
### eslint — ✅ exit 0
```
```
### next build — ✅ exit 0
```
├ ƒ /support/chat
├ ƒ /support/contact
├ ƒ /support/inbox
├ ƒ /support/inbox/[id]
└ ƒ /terms


ƒ Proxy (Middleware)

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand

```
- ℹ️ `next build` 가 sw.js CACHE_VERSION 을 갱신했으나 원복함 (읽기 전용 계약).

## 4. 삭제 잔해 — 사라진 모듈을 실제로 import 하는 코드

산문(docstring·주석) 언급은 세지 않는다. 이전 버전은 `services.artifacts` 의
`.` 가 정규식 임의문자라 `services/artifacts/foo.py` 라고 적힌 docstring 까지
매칭해 잔해 8곳·3곳을 보고했으나 실제 죽은 import 는 0건이었다.
```
services.artifacts       0곳
services.broker          0곳
services.trading         0곳
routes.artifacts         0곳
routes.daytrade          0곳
```

## 5. 프론트→백엔드 엔드포인트 계약

tsc·vitest 가 구조적으로 못 잡는 층. 프론트의 `/api/...` 는 단순 문자열 상수라
백엔드 라우트를 지워도 타입검사는 통과하고 런타임에만 404 가 난다.
```
DORMANT 8 declared in dormant_endpoints.txt (not counted)
STALE 11 dormant entries now served or renamed — prune the list:
  /api/artifacts/${id}/download
  /api/artifacts/${id}/preview
  /api/artifacts/${id}/read
  /api/artifacts/brag-card/preview
  /api/artifacts/by-month
  /api/artifacts/generate
  /api/artifacts/list
  /api/artifacts/living-mirror/download/${id}
  /api/artifacts/living-mirror/generate
  /api/artifacts/living-mirror/preview/${id}
  /api/artifacts/stats
ORPHANED 5 of 95 frontend endpoints have no backend route (134 rules parsed):
  endpoints.ts:99  /api/backtest/${ticker}
  endpoints.ts:47  /api/discover
  endpoints.ts:33  /api/portfolio/analytics
  endpoints.ts:81  /api/watchlist
  endpoints.ts:83  /api/watchlist/${id}
```

## 6. 규모
```
routes 파일    25
endpoints      136
services 파일  91
Python 줄      46124
tests 파일     176
```

---
읽기 전용 실행. 수정·커밋·푸시 없음.
