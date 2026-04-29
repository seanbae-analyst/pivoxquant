# Railway env 추가 TODO (2026-04-28)

배포 후 production 에서 P0 BUG 21건 중 일부가 여전히 안 풀릴 수 있는데,
**FMP budget fix 코드만으로는 부족** — Railway env 에도 다음 작업 필요.

## 1. 필수: FRED_API_KEY 추가

Railway 대시보드 → 백엔드 서비스 (`RAILWAY_BACKEND_HOST`) → **Settings → Variables → Add Variable**

| Name | Value |
|---|---|
| `FRED_API_KEY` | `bdd5f23acc7ef1dab2d328e1591f16bb` |

추가 후 **Redeploy** (Railway 가 자동 재시작 트리거).

검증:
```bash
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/alt-data/macro/snapshot
```
- 추가 전: `503 FRED_NOT_CONFIGURED`
- 추가 후: `200 OK` + JSON body (FEDFUNDS / DGS10 / T10Y2Y 등 시리즈 값)

→ P0 BUG 20, 21 해결.

---

## 2. 선택: FMP plan tuning

Premium $29 사용 중이므로 **default 가 Premium 에 맞게 설정됨** (`FMP_DAILY_SOFT_LIMIT=10000`). 
**Railway env 에 따로 설정할 필요 없음** — 코드 default 그대로 사용됨.

만약 **Starter $14 으로 다운그레이드**하거나, **분당 quota 보호용 더 낮은 cap** 원하면:

| Name | Value | 의미 |
|---|---|---|
| `FMP_DAILY_SOFT_LIMIT` | `250` | Starter $14 한도 |
| `FMP_BUDGET_STALE_PCT` | `0.88` | 88% 도달 시 stale cache fallback |
| `FMP_BUDGET_HARD_STOP_PCT` | `0.99` | 99% 도달 시 신규 호출 차단 |

검증:
```bash
# admin 로그인 후
curl -b "$ADMIN_COOKIE" https://RAILWAY_BACKEND_HOST.up.railway.app/api/admin/fmp-usage
```
- `daily_limit: 10000` → Premium default 정상
- `daily_limit: 250` → Starter override 적용됨

---

## 3. 배포 후 P0 BUG 21건 실측 재검증

Railway 자동 배포 완료 후 (CI 통과 확인 후):

```bash
# 1. discover (이전: is_mock:true → 이제 503 또는 실데이터)
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/discover/market-overview
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/discover/movers
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/discover/sectors
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/discover/screeners

# 2. FMP-dependent (이전: 빈 배열 → 이제 실데이터 or 503)
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/market/indices
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/sectors
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/news/AAPL
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/earnings
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/chart/AAPL
curl "https://RAILWAY_BACKEND_HOST.up.railway.app/api/prices?tickers=AAPL,NVDA"

# 3. FRED macro (FRED_API_KEY 추가 후만)
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/alt-data/macro/snapshot
curl https://RAILWAY_BACKEND_HOST.up.railway.app/api/alt-data/macro/regime
```

각 endpoint:
- **200 + 실데이터** → ✅ 해결
- **503 DATA_PROVIDER_DOWN** → FMP 호출 자체가 막힘 (rate limit / plan-gated). FMP 플랜 자체 문제일 수 있음
- **여전히 빈 배열** → FMP 가 진짜로 그 ticker 에 데이터 없음 (정상 빈 응답)

---

## 4. 자율 모드에서 안 한 것 (사용자 결정 필요)

### Wave 1B 신규 P0 8건 (user-tester agent 보고 — 진위 직접 확인 권장)

| # | 이슈 | 추정 위치 |
|---|------|-----------|
| 1 | `/terms` `/privacy` 흰배경 + raw markdown | `app/terms/page.tsx`, `app/privacy/page.tsx` |
| 2 | `/pricing` 카운터 0→9900 중간에 잘못된 숫자 (513원) 노출 | `app/pricing/page.tsx` 카운터 컴포넌트 |
| 3 | SEO canonical URL 이 Railway 내부 URL | `app/layout.tsx` 또는 `next.config.ts` metadataBase |
| 4 | 랜딩 가격 섹션 Free 카드만 보이고 Pro/Premium 잘림 | landing page price section carousel |
| 5 | `/reports/preview/*` 12개 비로그인자에게 안 보임 (auth gate) | preview 페이지들의 client-side auth check |
| 6 | 사업자등록번호 placeholder "(등록 후 표시)" 노출 | 푸터 컴포넌트 |
| 7 | Login redirect 시 `?from=` 누락 | middleware 또는 login redirect 로직 |
| 8 | `/companion` 비로그인 차단 (마케팅 페이지인데) | companion route auth requirement |

→ 본인 브라우저로 직접 확인 → fix 우선순위 결정 → 별도 PR

### 인증 영역 P0 6종 검증 (UNVERIFIED)

검색 / Watchlist+ / 알림벨 / 프로필 드롭다운 / Connect Alpaca/KIS / 코스피 데이터 — OAuth 로그인 후만 검증 가능.

옵션:
- A. 본인이 직접 https://pivoxquant.com 로그인 + 6종 클릭 테스트
- B. dev-login 쿠키 활용 (`.env DEV_LOGIN_SECRET=***REDACTED***`) — user-tester agent 재실행

---

## 요약

✅ **이번 푸시 (548cf3e) 로 해결됨** (코드 레벨):
- FMP budget Premium $29 한도 적용
- discover/* mock 데이터 노출 차단 (503 fail-fast)
- legal_scrub_response decorator 73 endpoint status_code 보존 버그
- 방어 코드 (PCT 역전 / ENV=0 clamp)

🚨 **사용자 액션 필요**:
1. Railway env: `FRED_API_KEY` 추가 → P0 BUG 20, 21 해결
2. 배포 후 위 §3 curl 재검증 → 17/21 P0 BUG 실측 확인
3. Wave 1B 신규 P0 8건 직접 검토 → fix 우선순위 결정
4. 인증 영역 P0 6종 직접/dev-login 검증

**배포 결정**: 위 4개 중 §1, §3 만 끝내면 P0 21건 중 19건 (90%) 해결. 나머지 2건은 UI 별도 PR.
