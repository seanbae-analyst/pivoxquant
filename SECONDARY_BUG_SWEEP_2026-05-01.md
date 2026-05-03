# PivoxQuant — Secondary Bug Sweep (2026-05-01)

> CRITICAL 5건 외에 잡을 수 있는 추가 버그/리스크 정리. 우선순위는 영향도 × 발생확률.

---

## 🔴 P0 — 출시 차단급

### B1. `.env`에 30+ 필수 키 누락 (배포 즉시 fail)

`.env`와 `.env.example` 비교 결과 **30개 이상 환경변수가 .env에 없음**. 일부는 prod에서 silent failure.

**누락된 키 + 영향**:

| 누락 키 | 영향 |
|---|---|
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_PREMIUM` | 결제 자체 불가 (이미 알려짐) |
| `PIVOX_BROKER_ENCRYPTION_KEY` | KIS 자격증명 암호화 키. 누락 시 broker 연결 저장 불가 또는 평문 저장 위험 |
| `CSRF_SECRET` | CSRF 보호 무효 또는 default 사용 |
| `DATABASE_URL` | prod에서 SQLite로 fallback → 데이터 손실 |
| `VAPID_PRIVATE_KEY`, `VAPID_EMAIL` | Web Push 작동 안 함 (silent) |
| `ADMIN_EMAILS` | admin endpoints 모두 404 — 본인이 admin 페이지 못 봄 |
| `RATELIMIT_STORAGE_URI` | rate-limit이 worker-local in-memory → gunicorn 다중 워커에서 우회 가능 |
| `CORS_ORIGINS` | CORS 미설정 → frontend에서 백엔드 호출 차단 또는 wildcard 위험 |
| `SESSION_COOKIE_DOMAIN` | 서브도메인 세션 공유 안 됨 |
| `FRONTEND_URL` | OAuth redirect 깨짐 |
| `BETA_PASSWORD` | 베타 게이트 우회 |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 네이버 로그인 미동작 (있다면) |
| `RUN_SCHEDULER` | APScheduler 실행 여부 컨트롤 — 누락 시 cron 안 돔 |

**조치**: prod 배포 전 `.env` 풀 채우기. 시크릿은 Railway/Vercel 환경변수에 직접.

### B2. Anthropic API credit 0 (5월 1일 HANDOVER 명시)

AI 기능 모두 fallback. 첫 유료 유저에게 "Premium AI 기능"이 작동 안 하면 즉시 환불 사태. 결제 연결 전 최소 $20 충전.

### B3. POST/PUT/DELETE 25+ 엔드포인트가 rate-limit 없음

`/api/alerts/*`, `/api/artifacts/*/trigger`, `/api/agent/query` 등 — 악의적 유저가 PDF 생성 cron을 분당 수백 번 트리거하면 FMP 402 즉시 + WeasyPrint CPU 폭주 + Anthropic credit 즉발.

**예시 (확인됨)**:
- `routes/agent.py:190` POST /query — 내부에 `_rate_limit_ok` 함수는 있지만 데코레이터 형태가 아님 (검증 필요)
- `routes/alerts.py:91-158` — read-all/clear/delete 모두 무제한
- `routes/artifacts.py:423,612,807,1013...` — 13개 trigger endpoint 모두 무제한

**조치**: `@trade_rate_limit` 또는 새 `@artifact_rate_limit` (분당 5회 등) 데코레이터 일괄 추가.

---

## 🟠 P1 — 사용자 경험 손상급

### B4. N+1 쿼리 4곳

루프 안에서 `SignalCache.query.get(ticker)` 또는 `.filter_by().first()` — 100개 포지션 시 100번 쿼리.

| 위치 | 패턴 |
|---|---|
| `routes/ai.py:96` | `for sc in SignalCache.query.all()` (전체 스캔) |
| `routes/ai.py:127` | 위와 동일 패턴 반복 |
| `routes/ai.py:402-403` | `for p in positions: SignalCache.query.get(p.ticker)` |
| `routes/alerts.py:177-178` | 위와 동일 |
| `routes/quant.py:161-162, 337-338` | 위와 동일 |

`routes/portfolio.py:50-54`는 이미 `cache_map = {c.ticker: c for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()}` 패턴으로 batch load함 — **이걸 다른 5곳에도 적용**.

### B5. 14개 routes 파일에 단위 테스트 없음

총 38개 라우트 파일 중 **14개 무테스트** (37%):

```
routes/admin_fmp.py
routes/admin_preview.py
routes/ai.py            ← AI 코어. 테스트 없음.
routes/autotrade.py     (disabled, 그래도 dead-code 위험)
routes/broker_oauth.py  ← KIS OAuth. 테스트 없음.
routes/command_center.py
routes/counterfactual.py
routes/daytrade.py      ← 데이트레이드 스캔. 테스트 없음.
routes/dev_auth.py
routes/health.py
routes/pre_trade.py
routes/push.py
routes/quant_composer.py
routes/simulate.py
```

특히 `ai.py`, `broker_oauth.py`, `daytrade.py`는 prod 트래픽 받는 라우트인데 0 테스트.

**조치**: 각 라우트에 minimum smoke test (`auth=401`, `200 happy path`) 추가. 1개당 ~30 lines.

### B6. SignalCache 전체 스캔 패턴 (`SignalCache.query.all()`)

`routes/ai.py:96, 127`에서 전체 SignalCache row 로드. 유저 1000명 × 평균 10 ticker = 10,000 row 메모리 적재. 응답 시간 + 메모리 폭주.

**조치**: `SignalCache.query.filter(SignalCache.ticker.in_(user_tickers)).all()` 형태로 사용자 스코프 한정.

### B7. CSP `unsafe-inline` (security TODO)

- `frontend/middleware.ts:140` — TODO: nonce-based로 마이그레이션
- `security.py:411` — TODO: CSP에서 `unsafe-inline` 제거

XSS 방어 약함. 외부 스크립트 인젝션 시 inline `<script>` 실행됨.

**조치**: Next.js 16의 nonce 패턴으로 전환. 1일 작업.

---

## 🟡 P2 — 잠재 리스크

### B8. `except Exception: pass` 다수 (silent failure)

`engine.py`, `quant_models.py`, `autotrader.py`, `realtime_service.py`, `ai_service.py`, `kis_token_manager.py` — 합쳐서 30+ 위치. 에러를 통째로 삼키면 production debug 불가능.

**최소 조치**: `except Exception: logger.exception(...)`로 변경 (Sentry로 자동 보고).

### B9. fx-historical TODO 미해결

`routes/counterfactual.py:486, 738` — 과거 거래도 *현재* USD/KRW 환율로 계산. 환율 큰 변동 시 counterfactual 결과 왜곡.

`fx_service`는 `get_rate()` 만 노출. 시계열 환율 fetch + 캐싱 추가 필요.

### B10. 회사명 우선 표시 (`_name_enrich`) — 누락 ticker 위험

5월 1일 commit `630b264`에서 추가. 새 long-tail KRX ticker 추가 시 mapping 누락하면 PDF에 종목코드만 표시.

**조치**: name_resolver fallback chain 검증 — pyKRX → us_stock_registry → ticker 그대로.

### B11. 테스트 1305개 중 skipif/xfail 3개

```
tests/test_dart_insider.py:296    @pytest.mark.skipif(...)
tests/test_quant.py:954-962        pytest.skip("routes/quant.py not found"...)
```

`test_quant.py`의 skip은 **파일 존재 확인 실패 시**인데, `routes/quant.py`는 존재함 → 영구 skip 가능성. 의도된 skip인지 확인.

### B12. Migration 20개 중 3 → 15 → 17 → 18 → 19 (헤드 다중)

`migrations/versions/` 파일이 selective load됐는데 003 → 015 사이의 숫자 일부 누락. branch + merge 흔적일 수 있음. `alembic heads` 다중 헤드면 재현 안 되는 deploy 버그 위험.

**조치**:
```bash
cd pivoxquant && alembic heads  # 헤드 1개여야 정상
alembic history  # 누락 검증
```

### B13. 미사용 imports / dead code (CLAUDE.md 인지)

- 미사용 shadcn 컴포넌트 9개
- 미사용 hooks 8개
- 미사용 types 13개
- `framer-motion`, `lightweight-charts` 패키지는 제거됐음

bundle size + maintenance 비용. 출시 전 일괄 정리 1일.

### B14. ESLint 17 errors (HANDOVER.md "보류항목")

코드 자체는 빌드되는데 lint errors 17개 잔존. CI에 lint 게이트 없으면 계속 누적. `frontend/` 안에서 `npx eslint . --quiet` 실행해 어떤 에러인지 카탈로그.

---

## 🟢 P3 — 폴리시 / 개선 여지

### B15. 5월 1일 commit 손상 (`fabb54d`, `630b264` 못 읽음)

`git log` 도중 "Could not read 630b2647... fatal: Failed to traverse parents of commit fabb54d..." 발생. **git repo objects 일부 손상** 가능성. `git fsck --full` 실행 권장.

### B16. 빈 파일 `frontend/src/components/portfolio/` 디렉토리 ls 출력

bash sandbox 이슈일 가능성 높지만, 혹시 inode 손상 상태면 빌드 시 중간에 실패할 수 있음. 호스트에서 `find frontend/src -type d -links 65535` 로 확인.

### B17. AddPositionModal vs add-position-modal 네이밍 (BUG #1 관련)

`portfolio.py` 백엔드는 두 엔드포인트 (`/position` 단수, `/positions` 복수)를 모두 노출. legacy + new shape 양쪽 호환. `endpoints.ts`에서 둘 다 export하는데 각자 어떤 컴포넌트가 어떤 걸 쓰는지 추적 필요. 한쪽 deprecate 권장.

### B18. WeasyPrint PDF 17개 → 메모리 풋프린트

매 cron마다 17개 PDF 동시 렌더링하면 Railway hobby plan(512MB) OOM 위험. 순차 렌더 + chunk 처리 검토.

### B19. 한국 ticker `.KS`/`.KQ` 일관성

backend는 `ticker.upper().endswith(".KS")` 패턴 다수. 사용자가 `005930` 만 입력하면? 자동 suffix 추가 로직이 어디서 일어나는지 (`name_resolver`, `data_fetcher`?) 검증.

### B20. realtime SSE EventSource 재연결

`frontend/src/lib/realtime.tsx` SSE provider — 백엔드 재시작 시 재연결 로직? exponential backoff? 무한 재연결 루프 시 백엔드 부하.

---

## 우선순위 별 1주 액션 플랜

**Day 1-2 (P0)**:
- B1: `.env` 30개 키 채우기 + Railway 환경변수 설정
- B2: Anthropic credit $50 충전
- B3: rate-limit 데코레이터 25개 엔드포인트 일괄 추가

**Day 3-4 (P1)**:
- B4 + B6: N+1 쿼리 5곳 batch load 패턴 적용
- B5: 14개 무테스트 라우트에 smoke test 1개씩 추가 (~7시간)

**Day 5 (P1 마무리)**:
- B7: CSP nonce 마이그레이션

**Day 6-7 (P2 일부)**:
- B8: silent except → logger.exception 일괄 변환 (sed)
- B12: alembic heads 검증 + 정리
- B11: skipif 영구 skip 의도 확인
- B14: ESLint 17 errors 처리

**출시 후 (P2-P3)**:
- B9, B10, B15-B20 점진 처리

---

## Claude Code에 줄 마스터 프롬프트 (선택)

CRITICAL 5개 끝난 후:

```
SECONDARY_BUG_SWEEP_2026-05-01.md 파일 읽고, P0 섹션(B1, B2, B3)만
순차 처리해. 각각 별도 commit + branch.

B1은 .env가 .env.example 형태로 자동 채워지면 안 됨 — 누락된 키 목록만
NEEDS_CONFIG.md 파일에 정리해서 사용자(CEO)가 직접 채우게 해.

B2는 코드 변경 X. NEEDS_CONFIG.md에 추가만.

B3은 routes/ 전체 grep 후 rate-limit 일괄 추가. fix(security): prefix.
```
