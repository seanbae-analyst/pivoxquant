# Railway env TODO (2026-04-29 갱신)

> **2026-04-29 변경**: Morning Brief 백엔드 전수 제거 (CEO 직접 결정).
> Morning Brief 전용 env 는 없었음 — Railway 변수 변경 불필요.
> 다만 **scheduler 가 더 이상 `morning_brief_daily` 잡을 등록하지 않음**.
> 다음 배포 후 Railway 로그에서 `scheduler.start jobs=...` 라인에
> `morning_brief_daily` 가 사라졌는지 확인 권장.

---

## 1. CEO 직접 추가 필요 — 누락된 env (현재 미설정)

| # | KEY | 용도 | 값 출처 (사용자가 직접 추가) |
|---|---|---|---|
| 1 | `FRED_API_KEY` | FRED 거시지표 (FEDFUNDS / DGS10 / VIX). 미설정 시 `/api/alt-data/macro/*` 503 반환 | <https://fred.stlouisfed.org/docs/api/api_key.html> 발급 후 입력 |
| 2 | `RUN_SCHEDULER` | 1로 설정한 단 1개 worker 만 APScheduler 가동. 미설정 시 weekly_memo / refresh / brag_card / earnings_prebrief 잡이 아예 안 돔 | `1` (단 dyno 가 N개일 때 1개에만) |
| 3 | `SENDGRID_API_KEY` | weekly_memo / earnings_prebrief / brag_card / kpi_dashboard 이메일 송신. 미설정 시 송신만 skip (기능 동작은 OK) | SendGrid 콘솔 → API Keys → Create |
| 4 | `STRIPE_API_KEY` | 결제 (Pro/Premium 구독). 미설정 시 `/api/billing/*` 502 반환 | Stripe 대시보드 → Developers → API keys |
| 5 | `STRIPE_WEBHOOK_SECRET` | Stripe webhook 서명 검증. 미설정 시 webhook 처리 거부 | Stripe → Developers → Webhooks → Signing secret |
| 6 | `STRIPE_PRO_PRICE_ID` | Pro 티어 ($9.9) 가격 매핑. 미설정 시 가격 페이지에서 결제 진입 불가 | Stripe → Products → Pro tier price → ID |
| 7 | `STRIPE_PREMIUM_PRICE_ID` | Premium 티어 ($19.9) 가격 매핑. 미설정 시 결제 진입 불가 | Stripe → Products → Premium tier price → ID |

추가 절차:
- Railway 대시보드 → 백엔드 서비스 (`<RAILWAY_SERVICE_NAME>`) → **Settings → Variables → Add Variable**
- 추가 후 자동 redeploy 트리거됨
- 검증: Railway 로그에서 `[startup]` 라인 + 위 §1 검증 curl 실행

---

## 2. 검증 curl (배포 후)

```bash
# Morning Brief 제거 검증 — 모두 404 또는 500 (의도)
curl -i <RAILWAY_BACKEND_URL>/api/morning-brief
curl -i <RAILWAY_BACKEND_URL>/api/brief/today
curl -i <RAILWAY_BACKEND_URL>/api/brief/archive
curl -i <RAILWAY_BACKEND_URL>/api/brief/generate-now

# 기대: 4건 모두 404 (Flask blueprint 등록 해제됨)

# FRED env 추가 후
curl <RAILWAY_BACKEND_URL>/api/alt-data/macro/snapshot
# 기대: 200 OK + JSON

# 스케줄러 잔재 확인 (Railway 로그)
# 검색: "scheduler.start"
# 기대: jobs=[...] 안에 morning_brief_daily 없음 / weekly_memo_sunday / refresh / brag_card_monthly / earnings_prebrief_scan 등만 있음
```

---

## 3. 미해결 (다음 작업)

- **DB 테이블 `morning_briefs` drop**: 코드 참조는 모두 제거됐으나 production DB 에는 테이블이 남아 있음. 다음 alembic migration 으로 drop:

  ```sql
  DROP TABLE IF EXISTS morning_briefs;
  ```

  단, drop 전 `pg_dump morning_briefs > backup.sql` 백업 권장. CEO 결정 후 실행.

- **frontend hooks/pages** (`useMorningBrief`, `/morning-brief` 페이지, `MorningBrief*` 타입): 백엔드 endpoint 가 사라졌으므로 frontend 호출 시 404. 별도 frontend dev 작업 필요 (이번 미션 백엔드 한정).

---

## 4. 이전 파일 보존
- `RAILWAY_ENV_TODO_2026-04-28.md` — FMP/discover P0 21건 분석 (참고용 보존)
- 이 파일이 최신 (2026-04-29)
