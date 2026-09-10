
# 야간 빌드 검증 — 2026-09-10 07:53 KST

브랜치: `chore/email-flags-on`
HEAD: `8f45b858 chore(pwa): realign the service-worker cache stamp`
미커밋: 2개 · untracked: 0개

## 1. 앱 부팅
- ✅ OK routes=121

## 2. 백엔드 테스트
### pytest — ✅ exit 0
```
    assert Artifact.query.get(art_id).opened_at is None

tests/test_sendgrid_webhook.py::test_signature_required_when_env_absent
  /Users/seanbae/Desktop/취준/pivoxquant/tests/test_sendgrid_webhook.py:470: LegacyAPIWarning: The Query.get() method is considered legacy as of the 1.x series of SQLAlchemy and becomes a legacy construct in 2.0. The method is now available as Session.get() (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    assert Artifact.query.get(art_id).opened_at is None

tests/test_sendgrid_webhook.py::test_valid_signature_accepted
  /Users/seanbae/Desktop/취준/pivoxquant/tests/test_sendgrid_webhook.py:514: LegacyAPIWarning: The Query.get() method is considered legacy as of the 1.x series of SQLAlchemy and becomes a legacy construct in 2.0. The method is now available as Session.get() (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    assert Artifact.query.get(art_id).opened_at is not None

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
==== 2071 passed, 18 skipped, 1 xfailed, 483 warnings in 328.95s (0:05:28) =====
```

## 3. 프론트엔드
- node: `/Users/seanbae/.nvm/versions/node/v20.20.2/bin` (v20.20.2)

### tsc — ✅ exit 0
```
```
### vitest — ✅ exit 0
```

 RUN  v4.1.5 /Users/seanbae/Desktop/취준/pivoxquant/frontend


 Test Files  51 passed (51)
      Tests  382 passed (382)
   Start at  07:59:42
   Duration  9.45s (transform 1.85s, setup 2.94s, import 10.29s, tests 9.94s, environment 31.40s)

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
DORMANT 5 declared in dormant_endpoints.txt (not counted)
OK 74 live frontend endpoints all match a backend route (119 rules parsed)
```

## 6. 규모
```
routes 파일    24
endpoints      121
services 파일  87
Python 줄      42025
tests 파일     163
```

---
읽기 전용 실행. 수정·커밋·푸시 없음.
<!-- verify-build:complete -->
