# PivoxQuant — 인수인계서 (2026-04-24 세션 종료 · v8 "Security bundle + Data robustness + Group Benchmark UI")

## 이 문서의 원칙
- **거짓 보고 금지**. 완료된 것은 완료, 미완은 미완.
- 내가 이번 세션 **잘못 보고했던 것**도 §10 에 기록.
- "대체로 OK" "거의 완료" 표현 금지. 숫자로.
- 확인 못한 건 "확인 필요" 라고 명시.

---

## 1. 🎯 세션 최종 commit (2026-04-24 · 11 commits 이번 세션 push + 1 overnight)

```
795b884  security: C1 multi-user AutoTrader isolation + H2-H6 bundle
2d0edb5  fix(fmp): stale-fallback cache for BRK.B / VTI / ARKK on budget exhaust
7251614  feat(market): KR indices source unification (KOSPI/KOSDAQ via KIS live)
d3a5892  feat(market): US indices proxy label (SPY/QQQ surfaced as proxies, ratio disabled)
9ba9eed  security(H1): fail-fast on missing PIVOX_BROKER_ENCRYPTION_KEY in prod
2cc4c41  fix(fmp): migrate to v3 + class-share retry (BRK.B → BRK-B fallback)
f11e598  fix: Risk/stale/KR/discover/alerts bundle (6 inline prod fixes)
d626632  perf: SWR dedup (home page 중복 호출 해소) + Risk flicker + proxy badge
217956a  feat(frontend): Persona v2 UI wiring + flip-card BUG-3 fix
59fb63c  ci: CI regression guards (forbidden term + hardcoded sample + import cycle)
(+ nightly bug hunt overnight: orphan cleanup 7 files)
(+ 이번 과제 커밋 예정: feat(frontend): shared PeerBenchmarkBlock + Reports 통합)
```

**Tests**: 1118/1118 pass (이전 세션 끝 기준, 이번 세션 추가 전)
**Frontend build**: 51/51 static routes · TS errors: 0 (npm run build 확인 완료 — §2 증거)
**Railway**: commit `795b884` 반영됨 (확인: `/api/health` 200 OK, CEO 본인 키 설정 후 H1 fail-fast 통과)

---

## 2. ✅ 진짜로 완료된 것 (증거: git log + 빌드 + 테스트)

| 영역 | 결과 | 증거 |
|---|---|---|
| **KIS Security C1** AutoTrader 싱글톤 user_id leak fix | ✅ | `795b884` · per-request `UserKISService`, 동시 유저 안전 · test_autotrade_isolation 12 cases pass |
| **KIS Security H1** 암호화 키 fail-fast | ✅ | `9ba9eed` · `PIVOX_BROKER_ENCRYPTION_KEY` 미설정 시 prod boot 거부 |
| KIS Security H3 로그 마스킹 (appkey/appsecret) | ✅ | `795b884` · `user_kis_service.py:178` `resp.text[:200]` → `_sanitize_kis_payload()` |
| KIS Security H4 로그 마스킹 (CANO 계좌번호) | ✅ | `795b884` · `kis_service.py:394` |
| KIS Security H5 주문 원본 주석 제거 | ✅ | `795b884` · `kis_service.py:431-518` 전부 `raise NotImplementedError` |
| KIS Security H6 CSRF 테스트 커버리지 | ✅ | `795b884` · test_autotrade_csrf 추가 4 cases |
| **H2 글로벌 KISService** (docstring 대응) | 🟡 **미완 — §3-B 참조** | docstring warning 만 처리. 실제 싱글톤 이용은 남아있음 (재검토 필요) |
| FMP v3 endpoint migration | ✅ | `2cc4c41` · v4 stable deprecated 에서 v3 로 fallback, class-share (BRK.B ↔ BRK-B) retry |
| FMP budget stale fallback | ✅ | `2d0edb5` · 402/429 시 last-good cache 로 degraded-mode 응답 (never crash) |
| KR indices source unification | ✅ | `7251614` · KOSPI/KOSDAQ Market 페이지가 KIS live API 단일 source |
| US indices proxy label | ✅ | `d3a5892` · SPY/QQQ 가 "proxy · ETF" 뱃지로 명시 (ratio conversion drift 제거) |
| Persona v2 UI 연결 | ✅ | `217956a` · `/profile` Identity 섹션에 `PersonaV2Card` 렌더 (persona-detail + benchmark 양쪽 wired) |
| BUG-3 flip card white flash | ✅ | `217956a` · `backface-visibility: hidden` + `will-change: transform` |
| SWR dedup (중복 호출 해소) | ✅ | `d626632` · `/api/auth/me` 5회+ → 1회, `/api/alerts` 5회+ → 1회 (dedupingInterval 300s) |
| Risk 페이지 flicker fix | ✅ | `d626632` · loading state 중첩 제거 |
| Risk/stale/KR/discover/alerts 6 inline fixes | ✅ | `f11e598` · discover empty state, alerts pagination overflow, KR volume formatting 등 |
| CI regression guards 3종 | ✅ | `59fb63c` · forbidden term scan / hardcoded sample scan / import-cycle detector |
| **Group Benchmark UI (이번 과제, 이 세션)** | ✅ | `frontend/src/components/shared/peer-benchmark-block.tsx` 신규 + Reports 페이지 통합 + persona-v2-card 리팩터 |

### §2-A Group Benchmark UI 상세 (이번 과제 증거)

**수정 파일 + 라인**:
- `frontend/src/components/shared/peer-benchmark-block.tsx` — **신규 280줄**. `usePersonaBenchmark(window)` 를 wrap 하는 공용 컴포넌트. N<20 suppression, observational 언어, Bronze/ivory 토큰, own-vs-group delta pill.
- `frontend/src/components/dashboard/persona-v2-card.tsx` — **-175줄**. 내부 `BenchmarkCard` / `BenchmarkCompareRow` 삭제, `<PeerBenchmarkBlock />` import 로 치환. `usePersonaBenchmark` import 제거. `MISTAKE_LABELS_KR` 삭제 (공용 컴포넌트로 이동).
- `frontend/src/app/(dashboard)/reports/page.tsx` — **+14줄**. `PeerBenchmarkBlock` import + DisclaimerBanner 아래에 렌더 (`declaredPersona` 있을 때만, kicker="Weekly Memo · peer context · 90-day").

**Weekly Memo 통합 지점**: Reports 페이지 (Weekly Memo / Brag Card 등 17개 artifact 카탈로그) 상단에 peer 비교 카드가 들어가 있어서, 유저가 Weekly Memo 를 열기 전에 본인 persona group 의 median 수치를 먼저 본다. 같은 컴포넌트가 `/profile` Persona v2 카드 안에도 이미 쓰이고 있음.

**제약 준수 확인**:
- N<20 suppressed: `usePersonaBenchmark` response 의 `available: false` + `reason: "insufficient_group_size"` 분기에서 "The {persona} group currently has fewer than 20 members — peer stats are withheld for privacy." 렌더
- Observational: 모든 문자열이 descriptive — "recommend/advice/buy/sell/추천/조언" 없음
- Bronze/ivory 토큰: `var(--pq-bronze)`, `var(--pq-ivory)` 만 사용, 신규 색상 없음

**PDF/HTML 템플릿 (`services/artifacts/templates/weekly_memo.html`) 수정은 이번 세션에 하지 않음** — Frontend Agent scope 외 (backend 수정 금지). PDF artifact 안에도 peer block 을 넣으려면 서비스 계층 수정이 필요하며, 이는 §5 P1 으로 남김.

**빌드 검증**:
```
✓ Compiled successfully in 12.1s
51 routes · 0 TS errors
```

---

## 3. 🔴 미완 / 알려진 문제 (거짓 없이)

### 3-A. 🔴 CRITICAL — FMP budget (오늘 소진)

- 이번 세션 중후반 FMP daily budget 소진됨 (`2d0edb5` 의 stale fallback 이 degraded-mode 로 서빙 중)
- 내일 UTC 00:00 에 quota reset 예상
- 이번 세션의 "verify-data" agent 검증 중 일부 API 경로가 stale cache 응답으로 통과 — 진짜 라이브 데이터 재검증은 내일 필요

### 3-B. 🔴 HIGH — H2 글로벌 KISService (재검토 필요)

- `795b884` 에서 **docstring** 만 수정. 실제 `services/container.py:25-29` 와 `autotrader.py:59-69` 의 글로벌 `KISService()` 싱글톤은 **그대로 남아있음**
- 이번 세션 agent 가 "H2 완료" 로 보고했지만 실제로는 docstring-only change. `test_kis_global_usage.py` 는 있지만 통과 여부 미확인
- CEO 가 KIS 약관 "1 App Key = 1 계좌" 위반 가능성 계속 관찰 필요
- **다음 세션 P0 재조정** 필요 — 진짜 per-request UserKISService 전환 or docstring 경고만 유지할지 결정

### 3-C. 🟠 HIGH — BRK.B 외 symbol 커버리지 (CEO 결정 대기)

- 이번 세션에 verify-data 초기 리포트가 "BRK.B / LLY / VTI / ARKK 전부 404" 라고 경보 → 조사 후 원인 2개: (1) FMP v4 stable 에서 해당 endpoint deprecated (→ `2cc4c41` 로 v3 migration), (2) 당일 FMP budget 일시 소진 (→ `2d0edb5` 로 fallback)
- v3 endpoint 가 일부 심볼에서는 불안정 — 예: BRK.B (class share) 는 `BRK-B` 로 변환 재시도 로직 필요 (`2cc4c41` 구현)
- LLY / VTI / ARKK 는 v3 에서 정상 (confirmed locally)
- **CEO 결정 필요**: FMP Starter → Ultimate tier 업그레이드 ($29 → $99/mo) vs. yfinance fallback 도입 (rate limit risk)

### 3-D. 🟠 HIGH — Persona v2 live QA pending

- `217956a` 로 UI 연결 완료. 로컬 pytest `test_persona_v2_ui.py` 5 cases pass
- **prod 실사용 QA 미실시**. Vercel 배포는 확인했지만 실제 로그인 → `/profile` 접근 → persona-detail 응답 → benchmark 응답 E2E 는 다음 세션에서 Claude-in-Chrome 으로 검증 필요

### 3-E. 🟡 MEDIUM — Dashboard Terminal Phase 2 (P1, 미착수)

- P1-8 에 올라와 있지만 이번 세션에 손 대지 않음
- portfolio / market / signals / risk / watchlist 가 아직 paper 디자인. Home 만 terminal 디자인으로 migrate 된 상태 (v7 세션)
- 다음 세션 작업 남음

### 3-F. 🟠 HIGH — Weekly Memo PDF artifact 본체에는 peer benchmark 미통합

- 이번 과제는 **frontend/React 계층**까지만 완료. 실제 PDF/HTML 템플릿 (`services/artifacts/templates/weekly_memo.html`) 에는 peer block 이 없음
- 즉 유저가 일요일 08:00 KST 에 이메일로 받는 PDF 안에는 peer median 비교가 없음
- 완전 통합하려면:
  1. `services/artifacts/weekly_memo_service.py` `MemoContext` 에 `peer_benchmark` 필드 추가
  2. `generate_for_user()` 에서 `services.profile.group_benchmark.compute_persona_stats()` 호출
  3. `templates/weekly_memo.html` 에 신규 섹션 (Part III 뒤, Colophon 전)
  4. N<20 suppression 템플릿 분기
- Backend 수정이라 Frontend Agent scope 밖 — §5 P1 에 등록

---

## 4. 📊 Production 상태

### Railway backend
- `/api/health` 200 OK (이번 세션 마지막 확인 시점)
- 커밋 `795b884` 반영 확인됨 (H1 fail-fast boot 통과 = CEO 가 `PIVOX_BROKER_ENCRYPTION_KEY` 설정했다는 증거)
- FMP budget 소진 상태 (§3-A)

### Vercel frontend
- 마지막 deployed commit `217956a` (Persona v2 UI). 이번 과제 커밋은 아직 미푸시.
- 이전 세션 (v7) 의 6 failed build 복구 완료 상태 유지

### 환경 변수 현황
- Railway `PIVOX_BROKER_ENCRYPTION_KEY` ✅ 설정됨 (H1 fail-fast 통과)
- Railway `RUN_SCHEDULER=1` ✅ (Morning Brief scheduler 동작 확인 필요 — 내일 6AM KST)
- Vercel `NEXT_PUBLIC_ALPACA_ENABLED=0` ⚠️ 확인 필요
- Vercel `NEXT_PUBLIC_BASE_URL=https://pivoxquant.com` ⚠️ 확인 필요
- Vercel `BETA_PASSWORD`, `BETA_SIGNING_SECRET` ⚠️ "Needs Attention" 재저장 필요 (v7 에서 계속 남은 과제)

---

## 5. 🎯 다음 세션 우선순위

### 🔴 P0 (즉시)
1. **FMP budget reset 후 verify-data 재실행** — 오늘 소진으로 검증 미완
2. **H2 글로벌 KISService 진짜 fix** — docstring 만 고친 상태. 재평가 후 either (a) per-request UserKISService 로 완전 전환, or (b) 현재 구조 정당화 + 경고 영구화
3. **Persona v2 prod E2E QA** — 로컬만 통과. Claude-in-Chrome 으로 실사용자 플로우 검증
4. **Weekly Memo PDF 템플릿에 peer benchmark 통합** (Backend) — 프론트만 된 상태이므로 PDF 에는 없음

### 🔴 P1 (이번 주)
5. **Dashboard Terminal Phase 2** — portfolio/market/signals/risk/watchlist terminal 디자인 migration
6. **BRK.B 외 symbol FMP tier 결정** (CEO 재무 판단: $29 → $99 vs. yfinance 병행)
7. **Morning Brief scheduler 첫 fire 검증** (6AM KST 이후 로그 확인)
8. **AAPL 404 prod verification** (v7 에서 미해결, 이번 세션 재확인 못함)

### 🟠 P2 (2주 내)
9. **Persona Evolution 시각화** (Wave 2 A) — 타임라인 + 글리프 전환
10. **Reclassify UX 고도화** (Wave 2 D)
11. **BUG-8 잔여 dedup** — home 은 처리했지만 /watchlist, /signals 에도 중복 호출 남았는지 재감사
12. **Group Benchmark Weekly Memo PDF 통합** (Backend work — 이 세션의 FE 과제 연장선)

### 🟡 P3 (런칭 준비)
13. Stripe Premium Plus + Founding Lifetime 등록 (CEO)
14. 상표 출원 (PivoxQuant + Pre-Trade Checklist)
15. 유사투자자문업 신고 (로펌 Q9 답 대기)
16. 이용약관/개인정보처리방침 V2 로펌 검토 후 배포

### 🔵 P3 (security/monitoring)
17. Sentry 통합 (런타임 에러 자동 수집)
18. `/api/ops/health-dashboard` 엔드포인트 (ops token auth — KOSPI/S&P/FMP quota gauge)
19. Dependabot 설정 + `anthropic` 버전 pin + `requirements.lock`
20. Nightly bug hunt 시스템 결과 리뷰 루프 — §9 참조

---

## 6. 🛡 법적 방어선 현황 (v8)

| 항목 | 상태 |
|---|---|
| DisclaimerBanner | ✅ 13 대시보드 + 7 feature pages + `/profile` + `/reports` |
| legal_filter 89 regex (scrub) | ✅ |
| legal_gate 22 advice regex | ✅ |
| FORBIDDEN_DIRECTIVE_TERMS (canonical 20) | ✅ `services/legal/forbidden_terms.py` |
| POSITIVE/NEGATIVE/NEUTRAL 라벨 | ✅ |
| KIS read-only / Alpaca 완전 제거 | ✅ (v7 확정) |
| **PeerBenchmarkBlock 익명성 (N≥20)** | ✅ **이번 세션** — `available: false` 분기 렌더 |
| **KIS Security C1 (싱글톤)** | ✅ **이번 세션 795b884** |
| **KIS Security H1 (암호화 키)** | ✅ **이번 세션 9ba9eed** |
| KIS Security H2 (글로벌 KISService) | 🟡 docstring 만 처리 — §3-B |
| KIS Security H3-H6 (로그 마스킹 / 주석 / CSRF) | ✅ 이번 세션 795b884 |
| Journal Companion 스펙 | ✅ (v7) |
| 개인정보처리방침 V2 draft | ✅ (v7) |
| 이용약관 V2 draft | ✅ (v7) |
| 상표 출원 | ⏳ 미출원 |
| 유사투자자문업 신고 | ⏳ 로펌 Q9 답 대기 |
| **Weekly Memo PDF peer benchmark** | ⏳ FE only — PDF 템플릿 통합 미완 (§3-F) |

---

## 7. 📦 이번 세션 생성된 주요 파일

### Frontend (이번 과제 + 이번 세션 전체)
```
src/components/shared/
  peer-benchmark-block.tsx          (신규 280줄 — 이번 과제)
src/components/dashboard/
  persona-v2-card.tsx                (-175줄 리팩터 — 이번 과제)
src/app/(dashboard)/reports/
  page.tsx                           (+14줄 peer 통합 — 이번 과제)
src/app/(dashboard)/profile/
  page.tsx                           (217956a — Persona v2 UI wire)
src/lib/cfo/hooks.ts                 (217956a — usePersonaBenchmark 추가)
```

### Backend (이번 세션 전체)
```
services/broker/
  user_kis_service.py                (795b884 — per-request isolation + H3 마스킹)
services/crypto_service.py           (9ba9eed — H1 fail-fast)
fmp_service.py                       (2cc4c41 + 2d0edb5 — v3 migration + stale fallback)
routes/market.py                     (7251614 + d3a5892 — KR/US indices)
routes/autotrade.py                  (795b884 — C1 isolation + H6 CSRF)
```

### Tests (새로 추가)
```
test_autotrade_isolation.py          (12 cases, C1 검증)
test_autotrade_csrf.py               (4 cases, H6)
test_fmp_v3_fallback.py              (BRK.B / class-share)
test_fmp_stale_cache.py              (402/429 degraded-mode)
test_kr_indices_unification.py
test_us_indices_proxy_label.py
test_persona_v2_ui.py                (5 cases, 217956a)
```

### CI
```
.github/workflows/
  ci-regression-guards.yml            (59fb63c · forbidden term + hardcoded + import cycle)
  nightly-bug-hunt.yml                (overnight agent, §9)
```

---

## 8. 💰 비용 임팩트 (이번 세션)

- Railway: 변화 없음 (같은 dyno size)
- Vercel: 변화 없음 (static + server functions)
- FMP: Starter tier ($29/mo) 유지 — 오늘 budget 소진은 verify-data agent 의 정상 검증 부하 (복구 내일)
- Claude API: 세션 내 약 ~3M 토큰 consumption (agent 병렬 운영 + night hunt)
- **CEO 재무 결정 대기**: FMP Ultimate ($99/mo) 업그레이드 — §3-C

---

## 9. 🛡 자율 bug hunt 시스템 (이번 세션 구축)

- `.github/workflows/nightly-bug-hunt.yml` — 매일 03:00 KST
- 3-phase: (1) legal scan + (2) data source health + (3) orphan/dead code scan
- 결과는 `reports/bug-hunt/YYYY-MM-DD.md` 에 artifact 로 저장
- **다음 세션 P3-20**: 결과 리뷰 루프 수립 필요 (현재는 저장만 하고 유저 notification 없음)
- 어젯밤 overnight run 에서 orphan 7 files 청소 + 1 forbidden term 잔재 검출 → 오늘 세션 시작 시 통합 완료

---

## 10. 🙏 정직 섹션 — 내가 이번 세션 잘못한 것

1. **5 commit push 때 H1 ancestor 동반 push 로 Railway 크래시 위험**
   → `9ba9eed` (H1 fail-fast) 를 push 하면서 `PIVOX_BROKER_ENCRYPTION_KEY` 가 Railway env 에 없는 상태였음
   → 이 상태로 deploy 되면 boot 시 `RuntimeError: missing encryption key` 로 서비스 전체 다운
   → CEO 가 즉시 Railway Variables 에 키를 추가해서 복구. 내가 push 전에 "env 설정 확인하라" 고 명시 안 함
   → 다음부턴 fail-fast 추가 PR 은 env 설정 instruction block 과 묶어서 push

2. **verify-data 초기 "BRK.B / LLY / VTI / ARKK 404" 보고가 일시적 FMP budget 이슈 + v3 deprecated endpoint 혼합 — 초기 조사 부실**
   → 처음엔 "심볼 커버리지 문제" 로 단정하고 심볼 whitelist 변경까지 생각했음
   → 실제로는 (a) v4 stable endpoint deprecated, (b) class-share symbol (BRK.B) ↔ (BRK-B) 변환 누락, (c) 그 시점 budget 일시 소진 — 3개가 섞임
   → 30분 추가 조사 후 3개 원인 분리 → `2cc4c41` + `2d0edb5` 2 commit 으로 정확히 분리 해결
   → 다음부턴 "전부 404" 류의 systemic 증상은 provider-side status page 먼저 확인

3. **각 fix 후 prod 재검증 없이 commit push 반복**
   → `f11e598` / `d626632` / `217956a` 연속 push 시 로컬 pytest 만 확인. Vercel preview 배포 링크로 실제 prod 행동 재검증 안 함
   → 다행히 이번엔 빌드 실패 없었지만, v7 세션의 "6 회 연속 Vercel fail" 재발 가능성 존재
   → 다음부턴 "prod critical" 변경 (SWR dedup, auth 관련) 은 preview deploy 링크 확인 후 main merge

4. **H2 "완료" 로 잘못 보고**
   → agent 가 `services/broker/user_kis_service.py` docstring 만 수정하고 "H2 done" 으로 보고. 내가 diff 만 빨리 보고 통과
   → 실제로는 `services/container.py` 싱글톤 KISService 그대로 남아있음
   → 유저의 "거짓보고하지마" 체크로 발견 → §3-B 에 정확히 기재, 다음 세션 P0 로 재조정
   → 교훈: security P1 "docstring-only" 는 거의 항상 insufficient. 실제 호출 경로 변경 확인 필수

5. **Group Benchmark UI 가 "Weekly Memo 통합" 으로 보고되지만 PDF 본체에는 없음**
   → 이번 과제 완료 보고 시 반드시 §3-F 로 명시 — 프론트 Reports 페이지 통합 = ✅ / PDF 템플릿 통합 = ❌
   → Agent scope (Frontend only) 상 제약이었지만 유저가 "artifact template 수정도 필요" 라고 명시했음. 다음 세션 backend work 필수

---

## 11. 🎯 다음 세션 시작 프롬프트

```
HANDOVER.md v8 읽고 이어서.

이번 세션 성과: 11 commits / 1118 tests baseline / 51 routes / KIS Security C1+H1+H3-H6 해결 / FMP v3 migration + stale fallback / KR/US indices 정합 / Persona v2 UI wired / Reports 에 PeerBenchmarkBlock 통합 / nightly bug hunt 시스템 구축.

P0 (다음 세션 즉시):
1. FMP budget reset 후 verify-data 재실행 (오늘 소진 상태)
2. H2 글로벌 KISService 진짜 fix (이번 세션은 docstring-only — §3-B)
3. Persona v2 prod E2E QA (Claude-in-Chrome)
4. Weekly Memo PDF 템플릿에 peer benchmark 통합 (backend — FE 만 완료된 상태 §3-F)

P1:
5. Dashboard Terminal Phase 2 (portfolio/market/signals/risk/watchlist)
6. BRK.B 외 심볼 FMP tier 결정 (CEO 재무: $29 → $99 vs yfinance)
7. Morning Brief scheduler 동작 검증 (6AM KST)
8. AAPL 404 prod verification

CEO 외부:
- FMP tier 업그레이드 결정
- 로펌 Q9 답 회수 + V2 draft 피드백 처리
- Vercel BETA_PASSWORD/BETA_SIGNING_SECRET "Needs Attention" 재저장
- Vercel NEXT_PUBLIC_ALPACA_ENABLED / BASE_URL 확인
```

---

**작성**: 2026-04-24 (v8 세션 종료)
**최신 commit**: (이번 과제 커밋 push 후 반영) · 직전 `795b884`
**프로덕션**: https://pivoxquant.com (베타 `***REDACTED***`)
**GitHub**: https://github.com/seanbae-analyst/pivoxquant/commits/main
**테스트**: 1118/1118 pass (세션 시작 기준) · 빌드 51/51 routes clean · TS 0 errors
