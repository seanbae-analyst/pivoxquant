# 야간 빌드 검증 — 2026-09-05 03:00 KST

브랜치: `fix/sweep-2026-09-04`
HEAD: `c20d7643 docs(blockers): backend is live on Render — B4/B6 done, B7 curl-only, R0 now ex`
미커밋: 1개 · untracked: 3개

## 1. 앱 부팅
- ✅ OK routes=121

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
==== 2000 passed, 18 skipped, 1 xfailed, 483 warnings in 1064.51s (0:17:44) ====
```

## 3. 프론트엔드
- node: `/Users/seanbae/.nvm/versions/node/v20.20.2/bin` (v20.20.2)

### tsc — ✅ exit 0
```
```
### vitest — ✅ exit 0
```
 [32m✓[39m src/components/portfolio/__tests__/to-position.test.ts [2m([22m[2m5 tests[22m[2m)[22m[32m 15[2mms[22m[39m
 [32m✓[39m src/lib/cfo/__tests__/coerce-pulse.test.ts [2m([22m[2m3 tests[22m[2m)[22m[32m 17[2mms[22m[39m
 [32m✓[39m src/lib/__tests__/initials.test.ts [2m([22m[2m3 tests[22m[2m)[22m[32m 21[2mms[22m[39m
 [32m✓[39m src/data/__tests__/onboarding-slider-seedable.test.ts [2m([22m[2m1 test[22m[2m)[22m[32m 5[2mms[22m[39m
 [32m✓[39m src/app/(dashboard)/__tests__/auth-redirect.test.ts [2m([22m[2m6 tests[22m[2m)[22m[32m 8[2mms[22m[39m
 [32m✓[39m src/__tests__/dashboard-redirect.test.ts [2m([22m[2m4 tests[22m[2m)[22m[32m 5[2mms[22m[39m

[2m Test Files [22m [1m[32m49 passed[39m[22m[90m (49)[39m
[2m      Tests [22m [1m[32m367 passed[39m[22m[90m (367)[39m
[2m   Start at [22m 03:18:25
[2m   Duration [22m 66.16s[2m (transform 11.09s, setup 18.00s, import 76.90s, tests 90.33s, environment 220.12s)[22m

```
### eslint — ✅ exit 0
```
```
### next build — ✅ exit 0
```
├ ƒ /support
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
OK 69 live frontend endpoints all match a backend route (119 rules parsed)
```

## 6. 규모
```
routes 파일    24
endpoints      121
services 파일  85
Python 줄      42399
tests 파일     160
```

---
읽기 전용 실행. 수정·커밋·푸시 없음.
