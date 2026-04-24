# PivoxQuant — 인수인계서 (2026-04-24 세션 종료 · v7 "Alpaca 제거 + Persona v2 + Simplify")

## 이 문서의 원칙
- **거짓 보고 금지**. 완료된 것은 완료, 미완은 미완.
- 내가 이번 세션 **잘못 보고했던 것**도 §10 에 기록.
- "대체로 OK" "거의 완료" 표현 금지. 숫자로.

---

## 1. 🎯 세션 최종 commit (10개 이번 세션 push)

```
d246a1a  fix(frontend): 4 terminal components (Vercel build fix)
8f71164  fix(frontend): /home terminal rebuild commit (Vercel unblock)
11c1550  refactor: simplify + error-proof (3-agent audit, -120 lines)
1013eb0  fix: 2 prod bugs (market-ticker static + alert Rec)
a2730a8  fix(market): revert wrong divergence guard + route conflict
7fcf3a2  chore(ci): 3 periodic scans (legal / security / smoke)
c2324e0  feat: Alpaca 완전 제거 + Persona v2 + Settings 재구조
685cdd3  fix: SW offline 503 + KR market accuracy
33d28aa  chore: cleanup MEDIUM orphans (7 files)
b027cf7  chore: cleanup HIGH + docs (7 orphans + 2 npm + docs 동기화)
7ad7e09  feat: P2 + a11y + legal sweep
```
(+ 직전 세션 1건 `1703dfc`)

**Tests**: 1056/1056 pass · **Frontend build**: 51/51 static routes · **TS errors**: 0

---

## 2. ✅ 진짜로 완료된 것 (증거: git log + 빌드 + 테스트)

| 영역 | 결과 | 증거 |
|---|---|---|
| P2 기능 완성 (HANDOVER v6 §3-D) | ✅ | landing-page 삭제 / CountUp / flip-deck / 40-model drawer / a11y focus trap (6 drawer) |
| Legal language sweep | ✅ | 11 파일 용어 치환 — "suggests raising cash" → "surfaces observation" 등 |
| SW 503 offline fallback fix | ✅ | `frontend/public/sw.js` sp-v3 → sp-v4, 3곳 throw 수정 |
| KR market 데이터 정확도 | ✅ | KOSPI 6475 (Yahoo 일치), 이전엔 divergence guard 가 stale FMP 로 덮어써서 틀림 |
| `/api/profile/*` route 충돌 | ✅ | `market_bp.route("/profile/<ticker>")` → `/market/profile/<ticker>` |
| `/api/notifications` endpoint | ✅ | alias of `/api/alerts` (17 tests) |
| Alpaca 완전 제거 (My Data 법 회피) | ✅ | ALPACA_ENABLED=0 env flag + 5 endpoint 503 + 6 service gated + UI 숨김 + i18n 비움 |
| Persona v2 (9-dim classifier) | ✅ | 22 tests, `/api/profile/persona-detail` + `/persona-explain` |
| Persona C (artifact 심화) | ✅ | Pre-Trade Checklist 56 질문 + persona_warnings + 5 macro |
| Persona E (group benchmark) | ✅ | PersonaGroupStats 모델 + 18 tests + 익명 N≥20 |
| Settings 재구조 | ✅ | `/profile` 신규 (807줄 Identity) + `/settings` 슬림화 (1198→770) |
| Notification bell color fix | ✅ | rgb(10,10,10) → bronze/ivory, WCAG AA 5.8:1+ |
| 3 periodic GitHub Actions | ✅ | daily-legal-scan / weekly-security-scan / daily-api-smoke |
| Simplify refactor (3-agent audit) | ✅ | FIFO 120줄 중복 제거 + TTL cache + SQL filter + N+1 fix + `_audit_all` fail-safe |
| legal draft V2 | ✅ | Terms V2 (§11-13 KIS read-only) + Privacy V2 (§10 KIS) + CHANGELOG |
| Morning Brief scheduler | 🟡 | Railway `RUN_SCHEDULER=1` 추가됨 — 내일 6AM KST 첫 fire 확인 필요 |

---

## 3. 🔴 미완 / 알려진 문제 (거짓 없이)

### 3-A. 🔴 CRITICAL — KIS Security P0 (C1)

**AutoTrader 싱글톤 user_id leak**
- `routes/autotrade.py:46-52`
- 주석에 `TODO(multi-user)` 명시됨 — 동시 요청 시 User A 요청이 User B 계좌로 기록 가능
- 현재 Procfile `--workers 1` 로 완화 중이지만 **scaling 시 깨짐**
- 자본시장법/개인정보보호법 위반 소지
- 수정: 싱글톤 제거 → per-request `UserKISService`

### 3-B. 🔴 HIGH — KIS Security P1 (6건)

| # | 파일:줄 | 이슈 |
|---|---|---|
| H1 | `services/crypto_service.py:56-62` | `PIVOX_BROKER_ENCRYPTION_KEY` 미설정 시 ephemeral → 재시작 시 전 유저 credentials 손실 |
| H2 | `autotrader.py:59-69`, `services/container.py:25-29` | 글로벌 `KISService()` 가 개발자 본인 KIS 키로 전체 유저 서빙 → 약관 "1 App Key = 1 계좌" 위반 |
| H3 | `services/broker/user_kis_service.py:178-182` | `resp.text[:200]` 로그에 `appkey`/`appsecret` 노출 가능 |
| H4 | `kis_service.py:394` | `get_balance` 에러 로그에 `CANO`(계좌번호) 노출 가능 |
| H5 | `kis_service.py:431-518` | `buy_order`/`sell_order` 원본 주석 코드 남아있음 — 실수 re-enable 위험 |
| H6 | `routes/autotrade.py:42-52` | CSRF 방어 테스트 부재 |

### 3-C. 🟠 HIGH — Production 미해결 (프론트 visual)

이번 세션에 SW fix 까지 했지만, Vercel 최신 배포 후 브라우저에서 직접 확인 필요:

- `/profile` 정상 로드 (404 아닌 페이지)
- `/settings` Alpaca 카드 완전 숨김
- 알림 벨 아이콘 bronze/ivory 색상 보임
- `/features/paper-trading` Alpaca 언급 전부 제거됨

### 3-D. 🟠 HIGH — US Indices ETF 값 문제 (설계상 제약)

- `/api/market/indices?region=us` 응답에서 `level` = ETF 가격 (SPY=$708) 으로 반환됨
- 실제 S&P 500 = ~7108 (10x 차이)
- 이유: FMP Starter tier 가 `^GSPC` 등 index symbol 미지원
- 코드 주석: "ratio conversion would drift"
- 해결 방향: FMP 상위 tier / yfinance 통합 / 라벨 명확화

### 3-E. 🟠 HIGH — AAPL 404 (미확인)

- 로컬 FMP_API_KEY 없어서 재현
- Prod 에서 실제 `/api/realtime/price/AAPL` 동작 확인 필요
- 동일 path 에서 NVDA 는 정상 ($199.64) — AAPL 만 실패

### 3-F. 🟠 HIGH — 이번 세션 배포 과정에서 내 실수 3회 (학습)

1. **Vercel build 6회 연속 실패** — `b027cf7` 에서 persona-card.tsx 삭제했는데 `home/page.tsx` 에서 여전히 import 중인 상태가 HEAD 에 있었음. Working tree 엔 uncommitted 로 import 제거됐지만 **commit 안 됨** → Vercel 이 HEAD 빌드하면서 missing module 에러. 해결: `8f71164` 로 home/page.tsx 커밋.
2. **4 terminal components 누락** — home/page.tsx 가 top-ticker/kpi-card/data-table/candlestick-chart 를 import 하지만 이 4개 파일이 untracked 였음. "이전 세션 것" 으로 판단하고 제외했는데 실제로는 필요. 해결: `d246a1a` 로 추가.
3. **KR market divergence guard 역효과** — `685cdd3` 의 divergence guard 가 KIS live 정확한 값을 stale FMP history 값으로 덮어씀. Yahoo 외부 검증으로 발견. 해결: `a2730a8` 로 가드 제거.

### 3-G. 🟡 MEDIUM — 보류된 버그

- BUG-3 flip card hover 시 white flash (3D 트랜지션 복잡, 수정 리스크)
- BUG-8 `/home` 에서 `/api/auth/me` 5회+, `/api/alerts` 5회+, `/api/portfolio` 7회+ 중복 호출 (SWR dedup 전략 필요)
- Dashboard Terminal Phase 2 (portfolio / market / signals / risk / watchlist paper → terminal 전환)

---

## 4. 📊 Production 상태

### Railway backend
- `/api/health` 200 OK
- commit `8f71164` 반영 여부 확인 필요 (env `RUN_SCHEDULER=1` 추가됨)

### Vercel frontend
- 마지막 commit `d246a1a` 배포 **성공 확인됨** (이번 세션 끝)
- 이전 6 commit 은 persona-card orphan 이슈로 **전부 fail** 했음 (2026-04-24 17:00 UTC 이후 복구)

### 환경 변수 추가/확인 필요
- Railway: `RUN_SCHEDULER=1` ✅ 추가됨 (Morning Brief scheduler 켜짐)
- Railway: `PIVOX_BROKER_ENCRYPTION_KEY` 설정 확인 필요 (H1)
- Vercel: `NEXT_PUBLIC_ALPACA_ENABLED=0` — 추가 확인 필요
- Vercel: `NEXT_PUBLIC_BASE_URL=https://pivoxquant.com` — canonical URL 수정 위해 필요
- Vercel: `BETA_PASSWORD`, `BETA_SIGNING_SECRET` "Needs Attention" 상태 — 재저장 필요

---

## 5. 🎯 다음 세션 우선순위

### 🔴 P0 (즉시)
1. **KIS Security C1** — AutoTrader 싱글톤 user_id leak fix (multi-worker 안전화)
2. **프론트 Persona v2 UI 연결** — 백엔드 endpoint 있음 (persona-detail/explain/benchmark) 프론트 미연결
3. **Morning Brief scheduler 동작 검증** — 내일 6AM KST 이후

### 🔴 P1 (이번 주)
4. KIS Security H1~H6 (암호화 키 / 글로벌 KISService / 로그 마스킹 / 주석 제거 / CSRF)
5. US indices ETF-as-level 문제 (yfinance 통합 or 라벨 명확화)
6. AAPL 404 원인 (prod verification)
7. Group Benchmark UI (Weekly Memo / Brag Card 통합)
8. Dashboard Terminal Phase 2 (portfolio/market/signals paper → terminal)

### 🟠 P2 (2주 내)
9. Persona Evolution 시각화 (Wave 2 A) — 타임라인 + 글리프 전환
10. Reclassify UX 고도화 (Wave 2 D)
11. BUG-3 flip card white flash 수정
12. BUG-8 SWR dedup 전략 (중복 API 호출 해소)

### 🟡 P3 (런칭 준비)
13. Stripe Premium Plus + Founding Lifetime 등록 (CEO)
14. 상표 출원 (PivoxQuant + Pre-Trade Checklist)
15. 유사투자자문업 신고 (로펌 Q9 답 후)
16. 이용약관/개인정보처리방침 V2 로펌 검토 후 배포

### 🔵 P3 (security/monitoring)
17. Sentry 통합 (런타임 에러 자동 수집)
18. `/api/ops/health-dashboard` 엔드포인트 (ops token auth, KOSPI/S&P/FMP quota 등)
19. Dependabot 설정 + `anthropic` 버전 pin + `requirements.lock`

---

## 6. 🛡 법적 방어선 현황 (v7)

| 항목 | 상태 |
|---|---|
| DisclaimerBanner | ✅ 13 대시보드 + 7 feature pages + `/profile` (신규) |
| legal_filter 89 regex (scrub) | ✅ |
| legal_gate 22 advice regex | ✅ |
| FORBIDDEN_DIRECTIVE_TERMS (canonical 20) | ✅ `services/legal/forbidden_terms.py` 통합 (이전엔 11/12 divergent) |
| POSITIVE/NEGATIVE/NEUTRAL 라벨 | ✅ |
| KIS read-only / **Alpaca 완전 제거** | ✅ 이번 세션 My Data 법 회피 |
| Dockerfile `AGENT_ENABLED=0` | ✅ |
| Dockerfile `ALPACA_ENABLED=0` (신규) | ✅ |
| Journal Companion 스펙 | ✅ SAFE_FEATURE_SPECS §6 |
| 개인정보처리방침 V2 draft | ✅ `reports/legal/DRAFT_PRIVACY_V2_2026-04-24.md` |
| 이용약관 V2 draft | ✅ `reports/legal/DRAFT_TERMS_V2_2026-04-24.md` |
| 로펌 Q&A 추가 5건 (multi-broker 포함) | ✅ `TERMS_V2_CHANGELOG_2026-04-24.md` |
| 상표 출원 | ⏳ 미출원 |
| 유사투자자문업 신고 | ⏳ 로펌 Q9 답 대기 |
| **KIS Security C1 (싱글톤)** | 🔴 **다음 세션 P0** |

---

## 7. 📦 이번 세션 생성된 주요 파일

### Backend (services/)
```
services/legal/
  __init__.py        · forbidden_terms.py    (canonical 20-term list)
services/profile/
  fifo_util.py       · common_util.py
  persona_classifier_v2.py   · group_benchmark.py
  [refactored] persona_analytics.py, rolling_metrics.py
services/artifacts/
  pre_trade_checklist_service.py   · persona_warnings.py
```

### Backend (routes + models)
```
routes/notifications.py  (alias of /api/alerts)
routes/profile.py        (+216 lines: persona-detail/explain/benchmark/benchmark-all)
routes/market.py         (BUG-3/4 fix + route rename)
routes/broker_oauth.py   (Alpaca kill switch)
models/persona_group_stats.py
migrations/versions/013_persona_group_stats.py
scripts/compute_group_stats.py   (weekly cron)
```

### Frontend
```
src/app/(dashboard)/profile/page.tsx      (807 lines, Identity/Persona)
src/app/(dashboard)/profile/layout.tsx
src/app/(dashboard)/home/page.tsx         (terminal rebuild)
src/components/terminal/
  top-ticker.tsx  · kpi-card.tsx  · data-table.tsx  · candlestick-chart.tsx
src/components/landing/
  engine-models-drawer.tsx  (40 models)
  report-flip-card.tsx      (3D flip + a11y)
src/lib/useFocusTrap.ts
```

### Tests (12 new)
```
test_alpaca_kill_switch.py  · test_persona_analytics_v2.py
test_group_benchmark.py     · test_persona_adapter_v2.py
test_pre_trade_checklist.py · test_notifications.py
test_no_hardcoded_samples.py · test_data_source_resolver.py
(+ updates to test_market.py, test_brag_card, test_earnings_prebrief, test_weekly_memo)
```

### GitHub Actions (3 new)
```
.github/workflows/
  daily-legal-scan.yml         (매일 09:15 KST)
  weekly-security-scan.yml     (매주 월요일 05:00 KST)
  daily-api-smoke.yml          (매일 06:00 KST)
```

### Reports (감사용)
```
reports/audit/
  CLEANUP_BRAND_2026-04-24.md
  CLEANUP_DEADCODE_CANDIDATES_2026-04-24.md
  CLEANUP_DOCS_2026-04-24.md
  SIMPLIFY_REUSE_2026-04-24.md
  SIMPLIFY_QUALITY_2026-04-24.md
  SIMPLIFY_EFFICIENCY_2026-04-24.md
  E2E_POST_SW_FIX_2026-04-24.md
  E2E_POST_DEPLOY_2026-04-24.md
  KIS_SECURITY_AUDIT_2026-04-24 (inline, 1 P0 + 6 P1 + 6 P2)
  DATA_POST_DEPLOY_2026-04-24.md (inline)
reports/legal/
  DRAFT_TERMS_V2_2026-04-24.md
  DRAFT_PRIVACY_V2_2026-04-24.md
  TERMS_V2_CHANGELOG_2026-04-24.md
  MULTI_BROKER_CONSULT_2026-04-24.md
reports/INDEX.md  · docs/INDEX.md
```

---

## 8. 💰 Alpaca 제거 임팩트 (CEO 결정 기록)

**결정 (2026-04-24)**: Alpaca 완전 제거, KIS 단일 broker.

**이유 (legal agent 리서치)**:
- "한 증권사만 연동" 명문 법 **없음**
- 하지만 **My Data 라이선스 회색지대** 존재:
  - 신용정보법 §2-9-2 "다수 정보제공자 수집·통합 제공" 정의에 걸릴 가능성
  - Alpaca + KIS 이중 = 위험, KIS 단일 = 안전 ("다수" 아님)
- KIS 약관 "시세정보 제3자 제공 금지" 는 별개 이슈 — 본인 키 본인 조회만 OK (현재 구조 안전)

**코드 영향**:
- US 가격 source 가 FMP 단일 의존 (Alpaca fallback 없어짐)
- autotrader paper trading 기능 비활성 (ALPACA_ENABLED=0)
- Legacy Alpaca DB 연결 row 는 read-only 유지 (migration 없음)

---

## 9. 🙏 정직 섹션 — 내가 잘못 보고했던 것

이번 세션 **내 실수** 명시:

1. **KR KOSPI 값 "fix 됐다" 거짓 보고**
   → 초기에 "KOSPI 2522 맞다" 고 주장 → 실제 test env 2026 KOSPI = 6475
   → 내가 짠 divergence guard 가 역효과: KIS 정확한 live 값을 stale FMP 로 덮어씀
   → verify-data agent 가 Yahoo 로 외부 검증해서 발견
   → 가드 제거 → 실제 Yahoo 값과 일치

2. **Vercel build 실패 진단 착오**
   → 6회 연속 실패. 처음엔 "Vercel env 문제", "cache 오염" 등 추측
   → 실제: `b027cf7` 에서 persona-card.tsx 삭제했는데 `home/page.tsx` 의 import 제거는 uncommitted
   → 즉 **내 cleanup 이 split commit 버그** 를 발생시켰음
   → dead code agent 가 working tree grep 해서 orphan 판정 — committed tree 와 다름

3. **4 terminal components 누락**
   → untracked 파일 4개 (top-ticker/kpi-card/data-table/candlestick-chart) 를 "이전 세션 것" 으로 잘못 판단하고 commit 에서 제외
   → 실제로는 home/page.tsx rebuild 가 이들을 import → Vercel 2차 실패
   → 3번째 commit 에서야 추가

4. **simplify agent 완료 후 검증 빠짐**
   → 처음엔 agent 주장 "9 steps done" 만 보고 넘어갈 뻔함
   → 유저의 "거짓보고하지마" 지적 후 독립 pytest 실행 → 1056 pass 확인

5. **Persona C test self-audit 실패 원인 진단**
   → "보유" 를 forbidden term 에 넣었다가 본인 copy 에 "보유 기간" 써서 self-block
   → 법적 단어 아님 ("매수/매도" 가 문제) — over-zealous
   → 제거 후 통과

6. **3 fix agent 가 모두 test fixture 에 작은 버그** (1씩)
   → Flask context 관리 / off-by-one / 하이픈 stale assertion
   → 코어 로직은 OK 였지만 agent 가 test 실행 못해서 발견 못함

7. **"추천" forbidden 단어 vs 면책 조항의 정당 사용**
   → Earnings prebrief test 에서 "추천" 발견 → "법 위반" 으로 오판
   → 실제: disclaimer 의 "...추천하지 않습니다" 라는 부정 문장
   → forbidden list 에서 "추천" 단독 제거, directive 결합만 유지

---

## 10. 🎯 다음 세션 시작 프롬프트

```
HANDOVER.md v7 읽고 이어서.

이번 세션 성과: 10 commits / 1056 tests / 51 routes / Alpaca 완전 제거 / Persona v2 백엔드 / 3 주기 CI / simplify refactor -120 lines.

P0 (다음 세션 즉시):
1. KIS Security C1 — AutoTrader 싱글톤 user_id leak fix
2. Persona v2 프론트 연결 (백엔드 endpoint 4개 있음, UI 미연결)
3. Morning Brief scheduler 첫 fire 확인 (6AM KST)

P1:
4. KIS Security H1~H6 (암호화 / 로그 마스킹 / CSRF)
5. US indices ETF-as-level 해결
6. AAPL 404 prod verification
7. Group Benchmark UI (Weekly Memo 통합)
8. Dashboard Terminal Phase 2

CEO 외부:
- 로펌 예약 확정 (Q1~Q20 + V2 draft 3건 + KIS Security findings 지참)
- Stripe Premium Plus + Founding Lifetime 등록
- Railway `PIVOX_BROKER_ENCRYPTION_KEY` 설정 확인
- Vercel `NEXT_PUBLIC_ALPACA_ENABLED=0`, `NEXT_PUBLIC_BASE_URL` 확인
- Vercel BETA_PASSWORD/BETA_SIGNING_SECRET "Needs Attention" 재저장
```

---

**작성**: 2026-04-24 (v7 세션 종료)
**최신 commit**: `d246a1a`
**프로덕션**: https://pivoxquant.com (베타 `***REDACTED***`)
**GitHub**: https://github.com/seanbae-analyst/pivoxquant/commits/main
**테스트**: 1056/1056 pass · 빌드 51/51 routes clean · TS 0 errors
