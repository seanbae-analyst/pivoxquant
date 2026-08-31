# 야간 빌드 검증 — 2026-08-31 03:00 KST

브랜치: `refactor/prune-artifacts`
HEAD: `e064118e refactor: delete the artefact tree, and fix what the mirror code got wrong`
미커밋: 1개 · untracked: 1개

## 1. 앱 부팅
- ✅ OK routes=249

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
=== 3237 passed, 19 skipped, 1 xfailed, 780 warnings in 17043.69s (4:44:03) ====
```

## 3. 프론트엔드
### tsc
```
/Users/seanbae/Desktop/취준/pivoxquant/scripts/nightly/verify_build.sh: line 56: npx: command not found
```
### vitest
```
/Users/seanbae/Desktop/취준/pivoxquant/scripts/nightly/verify_build.sh: line 60: npx: command not found
```
### eslint
```
/Users/seanbae/Desktop/취준/pivoxquant/scripts/nightly/verify_build.sh: line 64: npx: command not found
```
### next build
```
/Users/seanbae/Desktop/취준/pivoxquant/scripts/nightly/verify_build.sh: line 68: npm: command not found
```

## 4. 삭제 잔해 — 사라진 모듈을 가리키는 코드
```
services.artifacts       8곳
services.broker          1곳
services.trading         0곳
routes.artifacts         3곳
routes.daytrade          0곳
```

## 5. 규모
```
routes 파일    48
endpoints      246
services 파일  124
Python 줄      71645
tests 파일     232
```

---
읽기 전용 실행. 수정·커밋·푸시 없음.
