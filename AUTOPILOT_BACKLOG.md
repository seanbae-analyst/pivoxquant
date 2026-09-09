# Autopilot Backlog — CEO Review

P1 findings accumulated by the daily bug sweep. Not auto-fixed (detection-only or deferred). Check off when resolved.

## 2026-09-02 (daily-sweep, prod, Wed) — DETECTION-ONLY

**P0=2 · P1=5 · P2=6 · 자동수정 0건.** 미커밋 앱 소스 없음(dirty 서브모듈 + untracked QA 리포트만) — 하지만 자동수정을 안 한 이유는 가드가 아니라 **P0 2건 모두 코드 대상이 아니기 때문**이다(상세: `BUG_SWEEP_2026-09-02.md` §4).

스코프 주의: 08-31 prune 으로 라우트 9개가 삭제돼 **태스크 정의서의 페이지 목록이 stale** 이다. 실측 31 라우트로 재작성해 돌렸다. CAUS 레그도 `938bfcf4` 에서 폐기됨.
자동 스윕은 전부 green: virtual-user 516 calls/0 findings · 회귀가드 all passed(신규 0) · 야간 pytest 2010/0 · tsc 0 · 엔드포인트 계약 68/68 · 라이브 법규 스캔 위반 0.

### 🟥 P0 — 릴리스 게이트 (자동수정 불가, CEO 액션)
- [ ] **P0 — prod 백엔드 완전 불능.** Vercel `RAILWAY_BACKEND_URL` 이 삭제된 Railway 호스트를 가리키고 `NEXT_PUBLIC_API_URL` 은 빈 문자열이라 폴백된다(`next.config.ts:12-14`). 모든 `/api/*` → 404 `Application not found`. 신규 아님 — `docs/ops/backend-restore-2026-09-01.md` §5 의 기록된 항목. **CEO: ① Render 배포 → ② vercel env 교체 → redeploy.**
- [ ] **P0 — PIPA §28-8 국외이전 동의서가 삭제된 처리자(Railway)를 명시하고 실제 처리자(Render/Supabase)는 누락.** `frontend/src/content/privacy-ko.md:26,167,252` + `(auth)/signup/page.tsx:599` 라벨(`Anthropic / Vercel / Railway / Google / SendGrid`) + `lib/consents.ts:180-184` 주석. 해당 동의는 **[필수]** 로 가입 제출 조건(`signup/page.tsx:166`).
      ⚠️ **현재 실제 노출은 없다** — 백엔드 404 로 `POST /api/auth/signup` 자체가 실패(실측). 그러나 **Render 가 살아나는 순간 잘못된 고지로 가입이 재개**되므로 **컷오버 릴리스 게이트로 묶을 것.**
      자동수정 보류 사유: 올바른 처리자 목록은 Render/Supabase 리전 확정 후에야 정해지고, 문서 자체가 "변호사 검토 전 게시 금지" 초안이라 §28-8 필수 고지문을 에이전트가 단독 재작성하는 건 부적절.

### 🟠 P1 (5건 — 전부 소스+라이브 prod 재검증 완료)
- [x] ~~**P1 — 베타 게이트가 prod 에서 꺼져 있다(사이트 전면 공개).**~~ **CLOSED 2026-09-04 — CEO 결정 = 의도(무료 공개). 게이트·비번·env 전부 폐기.** Vercel prod 에 `BETA_PASSWORD` 없음(`BETA_SIGNING_SECRET` 은 있음). `middleware.ts:127` 이 env 없으면 게이트를 통째로 스킵 → 쿠키 없이 `/portfolio` 200. `/api/beta-auth` 는 500 "Beta gate is not configured". **의도(Stage 0 공개 전환)인지 설정 유실인지 근거가 없다 — CEO 결정 필요.**
- [ ] **P1 — `/admin` 진입 즉시 404.** `admin/page.tsx:19` 가 삭제된 `/admin/preview` 로 `router.replace`, `admin/layout.tsx:89` 도 동일 링크. 경로는 prune `47a5e8f3` 에서 삭제. 관리자 화면 전면 불능(유저 노출면 아님).
- [ ] **P1 — `/portfolio` 포지션 행 클릭이 자기 자신으로 되돌아온다.** `positions-table-v2.tsx:407` 이 삭제된 `/detail/[ticker]` 로 push, `next.config.ts:78` 이 그걸 `/portfolio` 로 308. 행은 `cursor:pointer`+hover(`:421-426`)로 클릭 가능해 보인다. 리다이렉트는 정상 — **호출부(핸들러+어피던스) 제거가 fix.**
- [ ] **P1 — `/support` FAQ 가 폐기된 유료 3단계 요금제를 안내.** `messages/ko.json:259-262`(+`en.json`) "무료/Pro 월 ₩9,900/Premium 월 ₩19,900" + 리다이렉트되는 `/pricing` 유도. Stripe 는 마스터 kill-switch 로 OFF, `/pricing` → `/mirror` 307(실측). 살 수 없는 플랜 광고 = 표시광고법 리스크.
- [ ] **P1 — `/support` 가 제거된 "AI 고객지원" 챗봇을 계속 광고.** `messages/ko.json:283-286` "로그인 후 「AI 고객지원에게 물어보기」". 챗봇은 2026-09-01 제거(`/support/chat` → `/support/contact` 308 실측). 로그인해도 1:1 문의/문의함만 존재.

### 🟡 P2 (6건 — 카운트 + 근거만)
- [ ] **P2 — `lib/demo.ts:302,304` 에 폐기된 점수화·시그널 어휘** (`"NVDA POSITIVE 신호"`, `score: 82`). dormant(`NEXT_PUBLIC_DEMO_MODE` 가 Vercel prod 에 없음) 이나 파일 용도가 "LinkedIn 쇼케이스" 라 플래그 하나면 공개 노출. + 삭제된 페이지용 픽스처 25개 잔존.
- [ ] **P2 — 면책 경로 맵 중복.** `(dashboard)/layout.tsx` `PATH_TO_TYPE` 에 `/mirror` 항목 2개. 선착순 매칭이라 지금은 정상이나 순서 바뀌면 조용히 잘못된 법적 문구.
- [ ] **P2 — 법규 필터에 `목표주가` 누락.** `legal_filter.py:87-88` 은 `목표가`·`목표 가격` 만. 실측 무변경 통과. 생성 경로 0건이라 노출 없음(백스톱 갭). 양성 용례 없어 추가 안전.
- [ ] **P2 — `/terms` 가 삭제된 시그널/점수 기능을 규정 중.** 변호사 큐.
- [ ] **P2 — `.claude/hooks/h6-handover-prepend.sh:34` 가 죽은 Railway 를 헬스체크** → 인수인계서에 잘못된 백엔드 상태를 계속 기록(`feedback_no_false_reports` 위반 경로).
- [ ] **P2 — 백로그 자체가 stale.** 열린 58건 중 **41건이 삭제된 라우트/서브시스템 참조.** 확인 사례: 07-12 P1 "realtime 가격 9h 오표기" 는 `price-with-timestamp.tsx` 와 원인 코드가 **둘 다 삭제돼 이미 무효**. **정합성 재조사 1회 필요.**

### 태스크 정의서(`SKILL.md`) 수정 필요
- [ ] 페이지 목록 → 현존 31 라우트 (현재 9개가 삭제된 경로)
- [ ] CAUS 레그 삭제 (`938bfcf4` 폐기)
- [ ] prod 호스트를 `https://www.pivoxquant.com` 으로 (apex 는 307)
- [ ] 베타 비번 절차 보류 (게이트 OFF, `/api/beta-auth` 500)
- [ ] Railway 참조 → Render + Supabase


## 2026-07-12 (daily-sweep, prod, Sun) — DETECTION-ONLY (uncommitted user work: `.claude/launch.json`, `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js`, `settings/_v2/page-v2.tsx`, `risk/v2/risk-gauge-grid.tsx`, `routes/watchlist.py`, submodule `ui-ux-pro-max`)

**P0=0 · P1(NEW)=4 · P2=2 · recurring(scheduler)=1(REFINED).** No auto-fix/commit (detection-only). ✅ **First FULL-authenticated prod sweep** — bug-hunter minted a legit CAUS sim-onboard session (`SIM_ONBOARD_SECRET` via `railway variables`) + drove headless Chromium (Playwright), so all 12 dashboard + 6 detail pages got real logged-in console/network/DOM checks (prior 10+ runs only reached public pages). Hermetic virtual sweep CLEAN (991 calls / 0 findings). Sunday artifact PDF full matrix **172 passed / 0 failed** (8m32s). CAUS rotated to authed **day-9** → honestly **SKIPPED (skipped_no_session)** (no cron `SIM_ONBOARD_SECRET`). Legal CLEAN (forbidden_terms 181 lines; DisclaimerBanner central `(dashboard)/layout.tsx`; 0 live BUY/SELL/HOLD/매수/매도 in detail+signals components; on-demand lookup healthy AAPL $315.32 / SPY $754.95 / QQQ $725.51 / VIXY $20.68). Backend health OK (`v47a2db735a50`, unchanged ≥12 days). Full detail: `BUG_SWEEP_2026-07-12.md`.

> ## ⚠️ 2026-09-01 — CAUS 폐기로 아래 항목 다수가 **자동 종료**됐다
>
> Continuous Autonomous User Simulation 전체가 삭제됐다 (CEO 결정). 시나리오가
> 겨냥하던 URL 10개 중 9개가 8-31 prune 으로 사라져 **없는 제품을 검사**하고
> 있었기 때문이다. 상세: `CLAUDE.md` 함정 §7.
>
> **이로써 닫히는 열린 항목** — 아래 본문은 이력이라 그대로 두되, 더 이상
> 작업 대상이 아니다:
> - `retire/repoint CAUS day-6 /pricing scenario` → **retire 로 종결**
> - `CAUS "fake-clean" via STALE session file` → 하니스 자체가 없어져 무의미
> - `CAUS auto-fix churn` P0 2건 → auto-fix 루프 삭제됨
> - 🔁 `SIM_ONBOARD_SECRET in cron env` (12회+ 반복) → **엔드포인트가 없다.**
>   이 시크릿은 이제 아무것도 마운트하지 않는다
> - `leftover branches caus-auto-fix/*` → 2026-09-01 삭제 완료 (둘 다 main 에
>   완전 병합돼 고유 커밋 0개였다)
>
> ⚠️ 남은 debris: `stash@{0}` (`caus-autofix-stash-a2dd7bba0044`) 는 **안 건드렸다**
> — stash 는 되돌리기 어려워 CEO 확인 후 `git stash drop` 할 것.


### P1 (NEW — all confirmed + root-caused this run; deferred to CEO, detection-only)
- [ ] **P1 — Fresh "realtime" prices mislabeled "9h ago" (stale/amber dot) on `/watchlist` + `/portfolio`.** Backend serializes naive `datetime.now().isoformat()` (NO `Z`, local wall-clock) in `services/data/realtime.py:621,671`; frontend `price-with-timestamp.tsx:56` has an *unguarded duplicate* `relativeTime()` (`new Date(iso)` parses naive string as browser-local KST) → ~9h skew vs the sibling `lib/relative-time.ts` which already got the UTC guard. Fix: emit UTC-aware ISO (`…+00:00`/`Z`) at source AND/OR route the component through the guarded shared helper. Confirmed (source read).
- [ ] **P1 — US index ribbon fabricates `0.00%` daily change when ETF history fetch is empty.** `_etf_snapshot()` (`routes/market.py:738`) defaults `change_pct=0.0`, only overwrites on successful history (`:787`), but still returns a dict when the *live quote* succeeds and history is empty (returns None only if BOTH fail) → QQQ/DIA/IWM/VIXY show a made-up 0.00% while SPY works. Fix: mark change as unknown/`null` (render `—`) instead of 0.0 when history unavailable. Confirmed (source read). Related to but distinct from the scheduler recurring item below (that's the *public cache-warm* path; this is the *authed live* path).
- [ ] **P1 — `/api/discover/movers?region=us` mislabels "no personal scan data" as "provider quota cooling off".** KR got an explicit `MOVERS_KR_NO_DATA` distinction (`routes/discover.py:318-338`); US falls through to the generic `_data_unavailable()` quota message (`:355`). Fix: add the symmetric US no-data code. Confirmed (source read).
- [ ] **P1 — Risk Board reports "composed / none breached" for a 0-position portfolio.** `derivePosture()` (`risk/_v2/page-v2.tsx:55`) maps `layersCount === 0` → `"composed"` (same as a genuinely safe portfolio), contradicting the honest "not enough holdings" empty-state copy on the same page. Fix: return a distinct empty/`insufficient` posture for 0 layers. Confirmed (source read).

### P2 (counted, deferred)
- [ ] **P2 (latent) — stale `price_display` field diverges from fresh `price` in `/api/watchlist`.** Not currently rendered so no user impact today; becomes a bug if a surface starts reading `price_display`. Files: `routes/watchlist.py` (uncommitted user WIP — leave to owner).
- [ ] **P2 — `/discover` Screeners shows "add holdings to unlock" while the backend screener is unconditionally unimplemented.** Misleading affordance (implies data-gated when it's feature-absent). Files: `routes/discover.py`, discover screener frontend.

### Recurring (REFINED this run — CEO/infra) — scheduler cache-warm partial recovery
- [ ] 🟥 **P1 (🔁 ~12 days, now NARROWED — theory revised) — scheduler cache-warm/FX jobs.** Live `/api/public/market-snapshot` (Railway direct) 07-12: **KR indices RECOVERED** (KOSPI 7475.94 / KOSDAQ 837.43, `observed_at 2026-07-11T05:33Z` = fresh) — this **DISPROVES** the 07-09 "shared try/except, US fails → KR skipped" theory. But **USD/KRW still frozen 2026-06-30T13:42Z** and **US index proxies ^GSPC/^IXIC/^VIX still `value:null`** — yet on-demand `/api/lookup/{SPY,QQQ,VIXY}` all return live prices → data source 100% fine, fault isolated to (a) the US-proxy branch of the warm job and (b) the FX-refresh job, failing *independently* of the (now-working) KR index warm. All items still flagged `is_stale:true` incl. fresh KR (staleness threshold ignores market-closed hours — minor). **CEO/infra: check Railway scheduler logs for `sched_fx_rate_refresh` + the US-proxy path in `_scheduled_indices_cache_warm` (`app.py:1462-1494`); `cache_warm:true` still misleadingly true while US null / FX 12-day stale.**

### Carried (unchanged — CEO action)
- _🔁 **`SIM_ONBOARD_SECRET` in cron env** — still absent from the scheduled-task env, so autonomous CAUS authed scenarios remain SKIPPED each rotation. NOTE: the secret **is** retrievable via `railway variables` (bug-hunter used it this run for a one-off session) — restoring it to the cron/task env would close the recurring SKIP gap._
- _Pre-existing debris (CEO cleanup): leftover branches `caus-auto-fix/6067d3b227f1` + `caus-auto-fix/a2dd7bba0044`, `stash@{0}`. P0/twin FX fix `38beb633` + `/risk` VaR×100 fix still local/undeployed (whole twin feature never shipped → no live corruption). DRAFT ToS/Privacy banners (external-lawyer gate)._

## 2026-07-09 (daily-sweep, prod, Thu) — DETECTION-ONLY (uncommitted user work: `.claude/launch.json`, `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js`, `settings/_v2/page-v2.tsx`, `risk/v2/risk-gauge-grid.tsx`, `routes/watchlist.py`, submodule `ui-ux-pro-max`)

**P0=0 · P1(recurring)=1 · P2=known-only · escalate(carried)=1.** No auto-fix/commit (detection-only). Hermetic virtual sweep CLEAN (991 calls / 0 findings). ✅ **Bug-hunter had a WORKING browser this session** (`playwright==1.59.0` + cached chromium) — first real-browser sweep in 7+ runs; public pages (`/`,`/login`,`/signup`,`/terms`,`/privacy`, 18 `/sample-reports/*`) got real console/network/DOM checks (0 page_errors, 0 NaN/undefined). BUT the 12 authed dashboard + 6 detail pages still uninspected as logged-in — root cause now precisely = **no test-account credential** (OAuth-only; `dev-login` 404 by design in prod), NOT "no browser tool". Legal CLEAN (DisclaimerBanner central `(dashboard)/layout.tsx:211`; 0 live BUY/SELL/HOLD/매수/매도; forbidden_terms 181 lines; KIS_READ_ONLY intact; auth wall 401 on all 8 probed endpoints, no leak). Backend health OK (`v47a2db735a50`, unchanged ≥9 days = same dead-scheduler signal). Full detail: `BUG_SWEEP_2026-07-09.md`.

### CAUS false positives this run (QA-tooling, NOT product bugs)
- CAUS rotated to **day-6 `/pricing`** (public scenario) and emitted 2 P1 ("0 tier names" + "DisclaimerBanner missing" on `/pricing`). **Both FALSE POSITIVES:** `GET /pricing` → `307` → `/home` (intentional billing-disabled redirect, free-launch Stage-0; the pricing page was removed by design). CAUS asserts on a defunct route → landing on `/home` has no tiers/disclaimer by design. Report: `docs/qa/auto-sim-reports/2026-07-09.md`.
- [ ] **P1 (NEW — QA tooling integrity, deferred) — retire/repoint CAUS day-6 `/pricing` scenario.** It asserts on `/pricing` which 307→/home; every rotation up will emit these 2 false P1s. Same stale-scenario class as prior CAUS integrity items. Files: `scripts/caus_daily_sweep.py` (day-6 scenario def / PUBLIC_SCENARIOS).

### P1 (recurring — CEO/infra)
- [ ] 🟥 **P1 (🔁 WORSENING — now 9+ days, root cause CONFIRMED-narrowed) — APScheduler warm-cache + FX jobs dead since ~2026-06-30 13:4x UTC.** `/api/public/market-snapshot` (07-09): KR items still frozen at **2026-06-30T13:08–13:41Z** (KOSPI 8476.48 / KOSDAQ 916.18 / USD/KRW 1541.85), US index proxies `^GSPC`/`^IXIC`/`^VIX` = `value:null, observed_at:null`, yet `cache_warm:true`. **Fault 100% isolated to the cache-warm job, not the data source** — all 6 test tickers fetch live *right now* (AAPL $314.14 / NVDA $203.13 / TSLA $390.83 / MSFT $384.18 / 삼성전자 ₩277,500 / 카카오 ₩34,650). `public_market_snapshot()` (`routes/market.py:1533`) is cache-only; cache populated by `_scheduled_indices_cache_warm` (`app.py:1462-1494`) which runs `warm_indices_cache("us")` then `("kr")` in one try/except (if "us" raises, "kr" never runs → both freeze same minute). `/api/health` version unchanged ≥9 days = `RUN_SCHEDULER=1` worker likely died ~06-30 13:4x UTC, no restart. **NOT code-fixable here — CEO/infra: check Railway logs ~2026-06-30 13:42 UTC for `sched_indices_cache_warm`/`sched_fx_rate_refresh` errors or a dead worker, then restart RUN_SCHEDULER.** Confidence 100% (isolation) / 85% (dead-worker). Frontend degrades gracefully (`market-ticker.tsx` renders `—`, never NaN). Files: `routes/market.py:34,1174-1343,1462,1533-1650`, `app.py:1462-1494,2285-2297`, `services/fx_service.py`.
  - sub (unchanged): market-snapshot `cache_warm:true` while US null / KR 9-day stale → misleading freshness flag. Don't count null/stale as cache-warm.

### Escalate-for-confirmation (50% — carried unchanged, NOT auto-fixed)
- [ ] **?? (50% conf, possibly by-design) — forbidden-terms SoT divergence candidate.** `services/legal/forbidden_terms.py` (181 lines, static artifact-copy substring block, excludes bare 익절/손절 to protect the "손절 속도" metric label) vs `services/legal_filter.py`'s independent `_REPLACEMENTS`/`_COMPLIANCE_FORBIDDEN_PATTERNS` (runtime AI-output regex scrubber). Re-read both this run: evidence still leans "intentional split-by-purpose" (docstrings frame it). **Do NOT touch `legal_filter.py` without explicit P0 legal violation (safety rail + `feedback_legal_filter_design`).** Recommend `investigate-bug`/`legal-kr-fintech` term-by-term diff to close. Files: `services/legal/forbidden_terms.py:1-33`, `services/legal_filter.py:39-80,595-612`.

- _Re-confirmed, NOT re-escalated (carried): **P2** `/api/beta-auth → 500 "Beta gate is not configured"` + sitewide gate OPEN (`BETA_PASSWORD` absent on Vercel by free-launch Stage-0 design — `middleware.ts:128` fails open, `GET /` + `GET /portfolio` → 200 no redirect). **P0/twin FX corruption** fix committed `38beb633` still NOT on prod (`47a2db73`) — but the whole KRW→USD twin feature (bug + fix) never deployed, so **no live corruption**; still worth next CEO push. **P1** `/risk` VaR/ES ×100 double-scale fix in uncommitted `risk-gauge-grid.tsx` WIP, undeployed. DRAFT ToS/Privacy banners (external-lawyer gate)._
- _**🔁 Recurring systemic gap (CEO action, 12th+ repeat):** restore `SIM_ONBOARD_SECRET` to cron env — its absence leaves authed CAUS scenarios SKIPPED + 12 auth-gated pages inspectable only via curl/API every run. Railway Variables holds the matching HMAC._
- _**Pre-existing debris (CEO cleanup, unchanged):** leftover branches `caus-auto-fix/6067d3b227f1` + `caus-auto-fix/a2dd7bba0044` and `stash@{0}`. CAUS Phase-4 dirty-tree auto-fix guard still outstanding._

## 2026-07-08 (daily-sweep, prod, Wed) — DETECTION-ONLY (uncommitted user work: `.claude/launch.json`, `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js`, `settings/_v2/page-v2.tsx`, `risk/v2/risk-gauge-grid.tsx`, `routes/watchlist.py`, submodule `ui-ux-pro-max`)

**P0=0 · P1(recurring)=1 · P2=known-only · escalate-for-confirm=1.** No auto-fix/commit (detection-only). Hermetic virtual sweep CLEAN (991 calls / 0 findings). CAUS `sim9` day-5 (`/reports` brag/memo/prebrief) honestly **SKIPPED (skipped_no_session)** — `SIM_ONBOARD_SECRET` still unset; the integrity fix now correctly writes SKIPPED instead of fake-clean (07-07's stale-session fake-clean path did **not** recur — sim9's session file is absent, not stale). Backend health OK (Railway `v47a2db735a50` — unchanged since ≥07-02, consistent with a scheduler worker that died once and never restarted). Legal regression CLEAN (DisclaimerBanner central in `(dashboard)/layout.tsx` wraps all 12 pages; 0 user-facing BUY/SELL/HOLD/매수/매도 — only 3 ban-documenting comments; auth wall 401 intact on all 12 backing endpoints; `dev-login` correctly 404 in prod). Bug-hunter ran HTTP/API + source-cross-ref only (**no browser tool bound — 7th+ consecutive session**; DOM/console/screenshot NOT verified). Full detail: `BUG_SWEEP_2026-07-08.md`.

### ✅ Status change — on-demand lookup path now FULLY healthy
- The 06-06→07-06 recurring **"prod US 주식·인덱스 데이터 전면 불능"** on-demand leg is now **RESOLVED**: today all 6 assigned test tickers return 200 with real prices (AAPL $313.02 / NVDA $197.05 / TSLA $405.02 / MSFT $391.87 / 삼성전자 ₩296,000 / 카카오 ₩35,400) **and** all US index proxies via `/api/lookup/{SPY,QQQ,DIA,IWM,VIXY}` return 200. FMP key is live/un-throttled for per-ticker quotes. The only remaining failure is the warm-cache background job (next item).

### P1 (updated — CEO/infra)
- [ ] 🟥 **P1 (🔁 WORSENING — now 8+ days, root cause CONFIRMED-narrowed) — APScheduler warm-cache + FX jobs dead since ~2026-06-30 13:4x UTC.** `/api/public/market-snapshot`: KR items (KOSPI/KOSDAQ/USDKRW) frozen at **2026-06-30T13:08–13:41Z**, US index proxies (`^GSPC`/`^IXIC`/`^VIX`) `value:null,observed_at:null`. **Fault is 100% isolated to the cache-warm job, not the data source** — identical live-fetch code path via `/api/lookup/{SPY,QQQ,VIXY}` + all 6 test tickers succeed *right now*. `public_market_snapshot()` (`routes/market.py:1533`) is cache-only; cache is populated by `_scheduled_indices_cache_warm` (`app.py:1462-1494`, id=`indices_cache_warm`) which calls `warm_indices_cache("us")` then `("kr")` in one try/except — if "us" raises, "kr" never runs (explains both freezing at the same minute). `/api/health` version unchanged ≥6 days = the `RUN_SCHEDULER=1` worker likely died ~06-30 13:4x UTC and never restarted. **NOT code-fixable here — CEO/infra: check Railway logs ~2026-06-30 13:42 UTC for `sched_indices_cache_warm`/`sched_fx_rate_refresh` errors or a dead worker, then restart the RUN_SCHEDULER worker.** Admin diag `/api/market/_diag/kr-indices` (403 to anon). Confidence 100% (isolation) / 85% (dead-worker root cause). Files: `routes/market.py:34,1174-1343,1462,1533-1650`, `app.py:1462-1494,2285-2297`, `services/fx_service.py`. Frontend degrades gracefully (`market-ticker.tsx:75-86` renders `—`, never NaN) → data-freshness/infra bug, not rendering.
  - sub (unchanged): market-snapshot `cache_warm:true` while US null / KR 8-day stale → misleading freshness flag. Don't count null/stale as cache-warm.

### Escalate-for-confirmation (50% — NOT auto-fixed; needs legal/investigate handoff)
- [ ] **?? (50% conf, possibly by-design) — forbidden-terms SoT divergence candidate.** `services/legal/forbidden_terms.py` (181 lines, self-documents as SoT for **artifact copy** directive terms) vs `services/legal_filter.py`'s own independently-defined `_REPLACEMENTS` (~39-80) + `_COMPLIANCE_FORBIDDEN_PATTERNS` (595-612), which do **not** import from `forbidden_terms.py`. May be legitimate scope-split-by-purpose (template copy vs real-time AI-output scrub) rather than accidental drift — the docstring itself frames the split. Also `_COMPLIANCE_FORBIDDEN_RE` (`legal_filter.py:612`) uses `re.IGNORECASE`, but only on English `buy|sell|recommend|advice|advise` hard-drop for AI-output (NOT the raw-prose `scrub_text` that `feedback_legal_filter_design.md` warns must stay case-sensitive) → likely safe. **Do NOT touch `legal_filter.py` without explicit P0 legal violation (safety rail).** Recommend `investigate-bug`/`legal-kr-fintech` term-by-term diff to confirm no genuine gap. Files: `services/legal/forbidden_terms.py:1-33`, `services/legal_filter.py:39-80,595-612`.

- _Re-confirmed, NOT re-escalated (carried): **P2** `/api/beta-auth → 500 "Beta gate is not configured"` + sitewide gate OPEN (`BETA_PASSWORD` absent on Vercel by free-launch Stage-0 design — `middleware.ts:128` fails open, `GET /` → 200 no redirect). **P0/twin FX corruption** fix committed `38beb633` still NOT on prod (`47a2db73`) — but verified the entire KRW→USD twin feature (bug + fix) never deployed, so **no live corruption**; still worth the next CEO push batch. **P1** `/risk` VaR/ES ×100 double-scale fix in uncommitted `risk-gauge-grid.tsx` WIP, undeployed. DRAFT ToS/Privacy banners (external-lawyer gate)._
- _**🔁 Recurring systemic gap (CEO action, 11th+ repeat):** restore `SIM_ONBOARD_SECRET` to cron env — its absence leaves authed CAUS scenarios SKIPPED + 12 auth-gated pages curl/API-shell-only every run. Railway Variables holds the matching HMAC._
- _**Pre-existing debris (CEO cleanup, unchanged):** leftover branches `caus-auto-fix/6067d3b227f1` + `caus-auto-fix/a2dd7bba0044` and `stash@{0}`. CAUS Phase-4 dirty-tree auto-fix guard still outstanding._

## 2026-07-07 (daily-sweep, prod, Tue) — DETECTION-ONLY (uncommitted user work: `.claude/launch.json`, `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js`, `settings/_v2/page-v2.tsx`, `risk/v2/risk-gauge-grid.tsx`, `routes/watchlist.py`, submodule `ui-ux-pro-max`)

**P0=0 · P1(new/updated)=2 · P2=known-only.** No auto-fix/commit (detection-only). Hermetic virtual sweep CLEAN (991 calls / 0 findings). CAUS `sim8` day-4 reported `ran/clean` — but see NEW tooling P1 below (stale-session fake-clean; not a real clean). Backend health OK (Railway `v47a2db735a50`, db ok, `missing_recommended:1` = known SENDGRID env). Legal regression CLEAN (DisclaimerBanner present on /signals; 0 user-facing BUY/SELL/HOLD/매수/매도; forbidden_terms 181 lines). Bug-hunter ran HTTP/API-only (no browser tool bound this session) + **retracted its own P1(metadata)/P2(sw.js) as false positives on cleaner re-fetch** — honest coverage gap, DOM/console/compliance-text NOT browser-verified. Full detail: `BUG_SWEEP_2026-07-07.md`.

### ✅ Status change — RESOLVED (was 8-day recurring P1)
- The 06-27→07-06 escalated **"prod US 주식·인덱스 데이터 전면 불능"** is **PARTIALLY RESOLVED**: `/api/lookup/{AAPL,NVDA,MSFT}` now returns **200 with fresh real prices** (AAPL $313.32) — was 404 for 8 days. KR `/api/lookup/005930.KS` → 200 삼성전자 ₩318,000 (localized name, not naked ticker). **Confirmed twice** (my Railway curl + bug-hunter www curl). The "US 개별 종목 404" leg is closed; the remaining failure is narrower (index cache only — see next). This also **falsifies the prior FMP-key/quota root-cause** for the lookup path: individual FMP quotes work, so the key is live and un-throttled for per-ticker lookups.

### P1 (updated — CEO/infra)
- [ ] 🟥 **P1 (🔁 WORSENING — now ~7 days, root cause NARROWED) — APScheduler warm-cache + FX jobs dead since ~2026-06-30 13:42 UTC.** `/api/public/market-snapshot` (07-07): KR items frozen at **2026-06-30T13:41–13:42Z** (KOSPI 8476.48 / KOSDAQ 916.18 / USD/KRW 1541.85), US indices `^GSPC`/`^IXIC`/`^VIX` = `value:null, observed_at:null`, yet `cache_warm:true`. **NEW isolating evidence:** individual quotes on BOTH markets are fresh (`/api/lookup` US+KR 200) → the fault is NOT FMP key/quota and NOT the quote pipeline — it is the **index-cache-warm + 1-min FX scheduler jobs**, which both froze at the *same minute* (06-30 13:4x UTC) = the `RUN_SCHEDULER=1` worker stopped ticking. US indices never populated (null); KR indices froze at last successful tick. `warm_indices_cache()` silently keeps the stale/null entry on failure. **CEO/infra: check Railway logs ~2026-06-30 13:42 UTC for `sched_indices_cache_warm` / `sched_fx_rate_refresh` errors or a dead worker, then restart RUN_SCHEDULER.** Confidence 90%. Files: `routes/market.py`, `app.py`, `services/fx_service.py`.
  - sub (unchanged): market-snapshot `cache_warm:true` while US null / KR 7-day stale → misleading freshness. Don't count null/stale as cache-warm.
- [ ] **P1 (NEW — QA tooling integrity, not a product bug) — CAUS "fake-clean" via STALE session file.** Today's CAUS (`sim8`, day-4 `/alerts` — a non-public authed scenario) reported `status: ran` / `_no findings — clean run_`, but `SIM_ONBOARD_SECRET` is unset AND `~/.pivoxquant-sim/sessions/sim8.json` is dated **May 17** (51 days old → cookie certainly expired). The 2026-06-12 integrity fix only guards the *missing*-session case (`elif not sess.exists()` → writes `SKIPPED`); a **present-but-expired** session file skips that guard (`caus_daily_sweep.py:788`) and proceeds to "run" against a login-redirect wall → 0 findings → false "clean". Same fake-clean class the 06-12 fix meant to kill, via a different path. **Fix (deferred, detection-only): add a session-file freshness/validity check** (mtime age cap + post-login assertion that the authed scenario actually reached authed DOM, else write `SKIPPED (stale_session)`). Until then, the authed CAUS leg is effectively non-covering AND silently green. Compounds the recurring `SIM_ONBOARD_SECRET`-missing gap below. Files: `scripts/caus_daily_sweep.py:756-808`.
- _Re-confirmed, NOT re-escalated (carried from 07-06): **P1** `/risk` VaR/ES gauge double-scale (×100) — fix in user's uncommitted `risk-gauge-grid.tsx` WIP, undeployed. **P0/twin FX corruption** fix committed at `38beb633` but not on prod (`47a2db73`) — CEO push+deploy still pending._
- _Re-confirmed, NOT re-escalated: **P2** `/api/beta-auth → 500 "Beta gate is not configured"` + sitewide gate OPEN (`BETA_PASSWORD` absent on Vercel by free-launch design; OAuth still gates dashboards). **P2** naked `.KS` in 5 input placeholders (functional hint, borderline). **P2** guest "게" avatar glyph pre-hydration. DRAFT ToS/Privacy banners (external-lawyer gate)._
- _**🔁 Recurring systemic gap (CEO action, 10th+ repeat):** restore `SIM_ONBOARD_SECRET` to cron env — its absence forces authed CAUS onto stale/no session (see NEW tooling P1) and leaves 12 auth-gated pages curl/API-shell-only every run. Railway Variables holds the matching HMAC._
- _**Pre-existing debris (CEO cleanup, unchanged):** leftover branches `caus-auto-fix/6067d3b227f1` + `caus-auto-fix/a2dd7bba0044` and `stash@{0}`. CAUS Phase-4 dirty-tree auto-fix guard still outstanding._

## 2026-07-06 (daily-sweep, prod) — DETECTION-ONLY (uncommitted user work: `.claude/launch.json`, `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js` (version-bump), `settings/_v2/page-v2.tsx`, `risk/v2/risk-gauge-grid.tsx`, `routes/watchlist.py`, submodule `ui-ux-pro-max`)

**P0=1 (deploy-gap, not code-fixable here) · P1=3 · P2=1.** No auto-fix/commit (detection-only + P0 fix already committed). Full detail: `BUG_SWEEP_2026-07-06.md`. Hermetic virtual sweep CLEAN (991 calls / 0 findings). CAUS `sim7` day-3 `ran`, raised 1 P1 (`/risk` 238-char "blank") = **FALSE POSITIVE** — `SIM_ONBOARD_SECRET` unset → unauthenticated session renders login-redirect shell (238 chars), not a real /risk bug; the accompanying `beta-gate auth 500` warning is the known P2 below. ✅ **Today's CAUS made NO git changes** (HEAD unchanged `38beb633`, 0 new commits/branches/stashes) — the 07-05 auto-fix-churn incident did **not** recur (auto-fix never fired: 0 P0 in CAUS). Legal regression CLEAN (0 user-facing BUY/SELL/HOLD/매수/매도; forbidden_terms 181 lines; `pytest test_forbidden_terms_sync test_legal_filter_forbidden_parity` → 4 passed). KIS read-only intact (`_place_order` is a hard-disabled `KIS_READ_ONLY` stub). Naked-ticker `<title>` gate CLEAN (`16eff2ce` deployed). Bug-hunter had no browser tool bound → 12 authed pages covered via curl/API + source-cross-ref only (honest coverage gap; recurring).

### 🟥 P0 — ESCALATE (deploy, NOT a code fix; CEO's separate-session push+deploy)
- [ ] 🟥 **P0 (twin FX data-corruption LIVE in prod — fix committed locally, undeployed).** `services/twin/twin_runner.py::reconcile_legacy_krw_positions()` gates its legacy-KRW→USD reconcile on a flat USD floor `_KRW_LEGACY_AVG_COST_FLOOR = 900`. A correctly-USD-booked high-priced KR share (e.g. LG생활건강 051900.KS at ₩1.5M → avg_cost ≈ $1086.96 ≥ 900) is misclassified as "legacy" and re-divided by ~1380 on the **next boot** → avg_cost corrupted to ~$0.79. `reconcile(dry_run=False)` runs inside `_do_migrations()` on **every prod boot** → any restart/redeploy can silently destroy legitimate bookings above ₩1,242,000. **Fix already committed at local HEAD `38beb633`** ("fix(twin): gate KRW→USD reconcile on a per-row marker") — **verified NOT an ancestor of `origin/main`; prod runs `47a2db73`, still vulnerable** (branch `fix/email-provider-retry` is 4 commits ahead of prod). **CEO action: push+deploy `38beb633` on priority** (merge/push is CEO's separate-session job per `feedback_push_workflow`). Confidence 100% (author's own commit + diff). File: `services/twin/twin_runner.py`.

### P1 (accumulated — CEO review)
- [ ] 🟥 **P1 (🔁 recurring — 06-27/06-30/07-01/07-02/07-03/07-05/07-06, 8th day, ESCALATE) — prod US 주식·인덱스 데이터 전면 불능.** Re-confirmed by curl 07-06: `/api/lookup/{AAPL,NVDA,TSLA,MSFT}` → 404; `/api/lookup/{005930.KS,035720.KS}` → 200 (KR healthy). Public `/api/public/market-snapshot` US indices `^GSPC`/`^IXIC`/`^VIX` all `value:null, observed_at:null`. Root cause chain unchanged (`fetcher.quick_lookup` Alpaca(OFF)→`fmp.get_quote` None when key missing/quota, soft-limit 250/day since `7e716091`). **Infra, not code-fixable here — CEO/infra: verify Railway `FMP_API_KEY` validity + quota.** ⚠️ `research_fmp_replacement.md`: FMP free tier likely violates commercial-display terms — key restoration ≠ license compliance (P0 open, legal). Files: `services/data/fetcher.py:362-410`, `services/data/fmp.py:298-303`.
  - sub (unchanged): market-snapshot `cache_warm:true` while US values null → misleading freshness. Don't count null as cache-warm.
- [ ] 🟥 **P1 (🔁 escalation of 07-03/07-05 — now WORSE, ~6 days) — KR 인덱스·FX 스냅샷 warm-cache 완전 동결 ≥4 KRX 세션.** `/api/public/market-snapshot` KR items still frozen at **2026-06-30T13:08–13:42Z (Tue)** as of 07-06 — unchanged across Wed 07-01 / Thu 07-02 / Fri 07-03 KRX sessions (KOSPI 8476.48, KOSDAQ 916.18, USD/KRW 1541.85). `/api/lookup/005930.KS` (independent path) returns fresh prices → KR quote pipeline alive; staleness isolated to `_indices_cache["kr_v2"]`. USD/KRW (independent 1-min FX job) frozen at the *same minute* as the KIS index job → **APScheduler worker (RUN_SCHEDULER=1) stopped ticking ~06-30 13:4x UTC**. `warm_indices_cache()` silently keeps stale entry on failure. **CEO/infra: check Railway logs ~06-30 13:40 UTC for `sched_fx_rate_refresh`/`sched_indices_cache_warm` failures or dead worker; restart RUN_SCHEDULER.** Admin diag `/api/market/_diag/kr-indices` (403 to anon). Confidence 85%. Files: `routes/market.py:1174-1343,1409`, `app.py:2238-2274`, `services/fx_service.py:492-517`.
- [ ] **P1 (NEW — real code bug, fix in user's UNCOMMITTED WIP, undeployed) — /risk VaR/ES gauges double-scale (×100) for sub-1% portfolios.** `RiskGaugeGrid` applied `Math.abs(raw) <= 1 ? raw*100 : raw` to `var_1d_pct`/`es_1d_pct` — but the backend **already** percent-scales them (`routes/risk.py:478,480`: `-np.percentile(...)*100`). A genuine sub-1% VaR (e.g. `0.6`) renders as **60%** instead of **0.60%** on the gauge + its 0–100% fill bar — only triggers for the *safest* portfolios (>1% unaffected), silently telling low-risk users they're at extreme tail risk. **Fix already written in the user's uncommitted working-tree diff** (`frontend/src/components/risk/v2/risk-gauge-grid.tsx`: drops the `<=1` heuristic → uses backend value as-is) but is uncommitted **and** prod (`47a2db73`) predates it → live in prod. Confidence 100% (backend contract + frontend diff cross-verified this run). **CEO: commit + deploy the risk-gauge-grid.tsx fix.** Files: `frontend/src/components/risk/v2/risk-gauge-grid.tsx:188-224`, `routes/risk.py:478-480`, `risk/_v2/page-v2.tsx:43,136`.
- [ ] **P2 (NEW — cosmetic, pre-hydration SSR) — Guest avatar badge renders broken 1-char "게" glyph for anonymous requests.** `curl` (no cookie) to any of the 12 dashboard routes returns 200 with dashboard chrome already in the SSR/RSC payload, showing a bronze avatar badge containing the single syllable **"게"** (first char of "게스트"/Guest). `initials()` in `profile-dropdown.tsx:35-46` assumes ≥2 space-separated words → degrades to 1 char for single-word/CJK names. Chrome mounts before the `if (!user) return null` client gate (`layout.tsx:166-176`) so it's in the literal server response (visible to crawlers/no-JS/slow clients; real browsers see a sub-second flash then redirect to `/login`). No PII, no legal label — cosmetic. Fix: `initials()` fall back to first 2 *characters* for single-word names. Files: `frontend/src/components/ui/profile-dropdown.tsx:35-46`, `frontend/src/app/(dashboard)/layout.tsx:166-176`.
- _Re-confirmed, NOT re-escalated: **P2** `/api/beta-auth → 500 "Beta gate is not configured"` + sitewide gate OPEN — independently re-verified this run: `BETA_PASSWORD` is genuinely **absent** from Vercel prod env (pulled 43 vars, `BETA_SIGNING_SECRET` present, `BETA_PASSWORD` missing) → `middleware.ts:128` skips the gate (fails open, site public) + the route 500s. Consistent with free-launch Stage-0 posture; no private data exposed (OAuth still gates dashboards). CEO call: set `BETA_PASSWORD` to restore gate, or retire the dead route. **P2** non-www sitemap/robots vs www canonical (SEO). DRAFT ToS/Privacy banners (external-lawyer gate, `SHIP_BLOCKERS.md`)._
- _**🔁 Recurring systemic gap (CEO action, 9th+ repeat):** restore `SIM_ONBOARD_SECRET` to cron env — its absence blocks authed CAUS + 12 auth-gated dashboard/detail pages every run (curl/API-shell coverage only). Railway Variables holds the matching HMAC._
- _**Pre-existing debris (CEO cleanup, from 07-03/07-05 incidents — NOT touched):** leftover branches `caus-auto-fix/6067d3b227f1` + `caus-auto-fix/a2dd7bba0044` and `stash@{0}` (caus-autofix-stash-a2dd7bba0044) persist. Root-cause fix for CAUS Phase-4 (gate auto-fix OFF on dirty tree / isolated scratch branch only) still outstanding._

## 2026-07-05 (daily-sweep, prod, Sunday) — DETECTION-ONLY (uncommitted user work: `.claude/launch.json`, `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js`, `settings/_v2/page-v2.tsx`, `risk/v2/risk-gauge-grid.tsx`, `routes/watchlist.py`, `services/twin/{__init__,twin_runner}.py`, submodule `ui-ux-pro-max`)

**P0=0 (product).** Full detail: `BUG_SWEEP_2026-07-05.md`.

- [ ] 🟥🟥 **P0 (HARNESS/TOOLING — CAUS auto-fix churn RECURRED & WORSE than 07-03) — CAUS committed onto the user's branch during a detection-only run.** Today's CAUS spawned `caus-auto-fix/a2dd7bba0044` + `stash@{0}` and its Phase-4 auto-fix loop made **4 commits (2026-07-05 18:40)** directly onto the user's checked-out branch `fix/email-provider-retry`, advancing HEAD `5491b0a6`→`24e5949c`. It committed the user's uncommitted WIP (`services/twin/*`, `settings/_v2/page-v2.tsx`, `risk/v2/risk-gauge-grid.tsx`, `routes/watchlist.py`) **and auto-generated new code** (`app.py` +22, `tests/test_twin_fx.py` +221) — files that were CLEAN at run-start. **On 07-03 this landed on a scratch branch; today it polluted the user's real branch = worse.** ✅ **Remediated by the sweep:** `git reset --mixed 5491b0a6` (non-destructive) → HEAD restored, all 10 WIP files back as uncommitted mods, `bug-hunt-2026-07-02-overnight.md` back to untracked, reflog retains the 4 commits. ⚠️ **Residual for CEO (NOT auto-cleaned — sweep won't delete files it didn't create):** auto-fix additions remain in the working tree entangled with WIP — `app.py` (M +22), untracked `tests/test_twin_fx.py` + `tests/test_twin_fx_audit_throwaway.py`, and `twin_runner.py` edits merged into the user's WIP (can't mechanically separate). **CEO actions:** (a) review the `app.py` / `test_twin_fx.py` auto-fix additions — keep (the twin KR-price-in-USD FX fix is a real known Pattern-7 issue) or discard; (b) 🟥 **ROOT-CAUSE FIX (2nd occurrence): CAUS Phase-4 auto-fix must be gated OFF on a dirty working tree, and must only ever operate on an isolated scratch branch — never commit onto the currently-checked-out user branch.** Recover the auto-fix commits if wanted: `git reset 24e5949c` (still in reflog). Leftover `caus-auto-fix/a2dd7bba0044` branch + `stash@{0}` left untouched as safety net.
 Hermetic virtual sweep CLEAN (991 calls / 0 findings). CAUS `sim6` day-2 authed → `ran`, 0 findings (transient beta-gate 500 warning; manual retest of `POST /beta/verify` → 200, `/home` → 200 = blip, not persistent). Legal regression scan CLEAN (0 user-facing BUY/SELL/HOLD/매수/매도; `journal` renders `intended_side` via `sideLabel()` only; DisclaimerBanner on journal+ai). All 12 page shells 200, auth wall intact. Bug-hunter had no browser tool bound again → 12 authed pages uncovered (public/API-shell only, honestly flagged).

- [ ] 🟥 **P1 (🔁 recurring — 06-27/06-30/07-01/07-02/07-03/07-05, ESCALATE) — prod US 주식·인덱스 데이터 전면 불능.** Re-confirmed 07-05: `/api/lookup/{AAPL,NVDA,TSLA,MSFT}` → 404; public `/api/public/market-snapshot` US indices (`^GSPC`/`^IXIC`/`^VIX`) all `value:null, observed_at:null`; KR lookup 200 (삼성전자/카카오). No relevant commit since 07-02. Root cause chain unchanged (`fetcher.quick_lookup` Alpaca(OFF)→`fmp.get_quote` None when key missing/quota, soft-limit 250/day). **CEO/infra: verify Railway `FMP_API_KEY` validity + quota.** ⚠️ `research_fmp_replacement.md`: FMP free tier likely violates commercial-display terms — key restoration ≠ license compliance (P0 open, legal). Files: `services/data/fetcher.py:362-410`, `services/data/fmp.py:298-303`.
  - sub (unchanged): market-snapshot `cache_warm:true` while US values null → misleading freshness. Don't count null as cache-warm.
- [ ] 🟥 **P1 (🔁 escalation of 07-03 — now WORSE) — KR 인덱스 스냅샷 warm-cache 동결 ~5일 / ≥3 거래일.** `/api/public/market-snapshot` KR items (`^KS11` 8476.48, `^KQ11` 916.18, `USDKRW` 1541.85) all still frozen at **2026-06-30T13:41–13:42Z (Tue)** as of 07-05 — unchanged across Wed 07-01 / Thu 07-02 / Fri 07-03 KRX sessions. 07-03 gap was ~2.2d; now ~5 calendar days → "TTL lag" untenable, warm job not firing at all. `/api/lookup/005930.KS` (independent path) returns fresh prices → KR quote pipeline alive; staleness isolated to `_indices_cache["kr_v2"]`. USD/KRW (independent 1-min FX job) frozen at the *same minute* as the KIS index job → **APScheduler worker (RUN_SCHEDULER=1) stopped ticking ~06-30 13:4x UTC** (deploy/restart/crash). `warm_indices_cache()` silently keeps stale entry on failure (no signal beyond `is_stale:true`). **CEO/infra: check Railway logs ~06-30 13:40 UTC for `sched_fx_rate_refresh`/`sched_indices_cache_warm` failures or worker restart; restart RUN_SCHEDULER worker if dead.** Admin diag: `/api/market/_diag/kr-indices`. Confidence 85%. Files: `routes/market.py:1174-1343,1409`, `app.py:2238-2274`, `services/fx_service.py:492-517`.
- _**🔁 Recurring systemic gap (CEO action, 8th+ repeat):** restore `SIM_ONBOARD_SECRET` to cron env — its absence blocks authed CAUS + 12 auth-gated dashboard/detail pages every run, AND (07-03) produced false P0s + auto-fix churn. Railway Variables holds the matching HMAC._
- _Re-confirmed, NOT re-escalated: **P2** non-www sitemap/robots vs www canonical (SEO-only). **P2** `/api/beta-auth → 500` + gate OPEN (intentional Stage-0 demo). DRAFT ToS/Privacy banners (external-lawyer gate, `SHIP_BLOCKERS.md`)._

## 2026-07-03 (daily-sweep, prod) — DETECTION-ONLY (uncommitted user work: `.claude/launch.json`, `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js`, `settings/_v2/page-v2.tsx`, `risk/v2/risk-gauge-grid.tsx`, `routes/watchlist.py`, submodule `ui-ux-pro-max`)

**P0=0 (real). No product auto-fix (detection-only run).** Hermetic virtual sweep CLEAN (991 calls / 0 findings). Bug-hunter legal-regression scan CLEAN (0 user-facing BUY/SELL/HOLD/매수/매도; BUY/SELL grep hits are internal `TradeHistory.action` ledger fields, expected; DisclaimerBanner + forbidden_terms SoT intact). Sitemap/robots/health/KR-lookup all nominal.

- [ ] 🟥 **P1 (NEW, genuine regression — bug-hunter, 80% conf) — KR public market-snapshot cache frozen ~2.2 days across 2 trading sessions.** `/api/public/market-snapshot` KR items (`^KS11` 8476.48, `^KQ11` 916.18, `USDKRW` 1541.85) all carry `observed_at` frozen at **2026-06-30T13:41–13:42Z (Tue)**, unchanged today (2026-07-03 Thu) — spanning Wed 07-01 + Thu 07-02 trading days. **Distinct from the US/FMP outage** (this is the KR side additionally going stale). Isolation: `/api/lookup/005930.KS|000660.KS|035720.KS` (different code path) returns **fresh, differing** prices each call → the KIS/KR quote pipeline itself is alive; staleness is isolated to the `_indices_cache["kr_v2"]` snapshot layer feeding the landing ticker. Strongest signal: **USD/KRW (own independent 1-min FMP/exchangerate-api scheduler job) froze at the identical Tue timestamp** as the KIS-backed index warm job → both refresh paths dying to the minute points to **the APScheduler worker (RUN_SCHEDULER=1) stopping ticking ~2026-06-30 13:4x UTC** (deploy/restart/crash), not two upstreams failing simultaneously. `warm_indices_cache()` (`routes/market.py:1309-1342`) silently keeps the stale entry on upstream failure (no error surfaced beyond `is_stale:true`) → zero visible signal. **NOT code-fixable from here — CEO/infra action:** check Railway logs around 06-30 13:40 UTC for `[fx-scheduler] USD/KRW STALE` / `sched_fx_rate_refresh` / `sched_indices_cache_warm` failures or a worker restart; if RUN_SCHEDULER worker died, restart it. Also `/api/market/_diag/kr-indices` (`routes/market.py:1409`) is admin-gated for exactly this. Files: `routes/market.py:1174-1343,1409,1533-1660`, `app.py:1435-1465,2238-2274`, `services/fx_service.py:492-517`. (Minor doc-drift noted alongside: `routes/market.py:1521-1531` comment claims "no dedicated cache-warm job exists" but one was added at `app.py:2258-2274` — stale comment, cleanup only.)

- [ ] **P1 (NEW — sweep-harness bug, self-inflicted noise) — CAUS auto-fix fired on a FALSE P0 → churn + spurious GitHub issue #532.** Today's CAUS `sim4` Day-0 authenticated scenario reported **P0 `/api/me` 403** and auto-filed [issue #532](https://github.com/seanbae-analyst/pivoxquant/issues/532), then the Phase-4 auto-fix loop ran `claude -p`, hit max-turns(30), and left a stray branch `caus-auto-fix/6067d3b227f1` + stashed the user's uncommitted work. **Root cause = harness, not prod:** `SIM_ONBOARD_SECRET` is unset so no fresh session can be minted, but a **7-week-stale session file `~/.pivoxquant-sim/sessions/sim4.json` (mtime May 13)** exists → `sess.exists()` is true → the scenario RAN with a dead cookie instead of SKIPPING → guaranteed 403. Compounding: the scenario probes `/api/me` which **was never a real route** (no-cookie → 404; correct endpoint is `/api/auth/me` per `routes/auth.py::me` + `ENDPOINTS.auth.me`). The auto-fix's (incomplete) insight is preserved at `docs/qa/auto-fix-log/2026-07-03-caus-day0-api-me-endpoint-fix.patch`. **Remediation (CEO, deliberate — not auto-applied): (a)** close/ignore issue #532 (false positive); **(b)** delete the 5 stale `~/.pivoxquant-sim/sessions/sim{4..8}.json` files (all May 13-17) so authed scenarios SKIP cleanly until `SIM_ONBOARD_SECRET` restored, OR make CAUS skip authed scenarios when `SIM_ONBOARD_SECRET` is unset **even if a session file exists** (age-check the cookie); **(c)** apply the saved patch to fix the `/api/me`→`/api/auth/me` scenario endpoint. Repo already restored to pre-sweep state (user branch `fix/email-provider-retry` @ `5491b0a6`, all 8 files re-applied, phantom stash dropped).

- [ ] 🟥 **P1 (🔁 recurring — day 7+, ESCALATE) — prod US 주식·인덱스 데이터 전면 불능.** Re-confirmed 07-03: `/api/lookup/{AAPL,NVDA,TSLA,MSFT}` all → 404; public `/api/public/market-snapshot` US indices (`^GSPC`/`^IXIC`/`^VIX`) all `value:null, observed_at:null`; KR lookup 200. Root cause chain unchanged (`fetcher.quick_lookup` Alpaca(OFF)→`fmp.get_quote` returns None when key missing/quota). **CEO/infra action:** verify Railway `FMP_API_KEY` validity + quota. ⚠️ separately `research_fmp_replacement.md`: FMP free tier likely violates commercial-display terms — key restoration ≠ license compliance (P0 open). Files: `services/data/fetcher.py:362-410`, `services/data/fmp.py:299-301`.
  - sub (unchanged): market-snapshot `cache_warm:true` while US values null → misleading freshness. Don't count null as cache-warm.

- _Re-confirmed, NOT re-escalated: **P2** non-www `sitemap.xml`/`robots.txt` Host/Sitemap vs www canonical (SEO-only). **P2** `morning-brief-plus` gallery orphan (not re-verified today). **P2** `/api/beta-auth → 500` + gate OPEN (intentional Stage-0 demo). DRAFT ToS/Privacy banners (external-lawyer gate, `SHIP_BLOCKERS.md`)._
- _**🔁 Recurring systemic gap (CEO action, 7th+ repeat):** restore `SIM_ONBOARD_SECRET` to cron env — its absence both blocks authed CAUS coverage (12 auth-gated dashboard/detail pages unverified every run) AND now actively produces false P0s + auto-fix churn (see harness bug above). Railway Variables holds the matching HMAC._

## 2026-07-02 (daily-sweep, prod) — DETECTION-ONLY (uncommitted user work: `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js`, submodule `.claude/skills/ui-ux-pro-max`)

**P0=0. No auto-fix (detection-only run).** Hermetic sweeps clean (virtual 991 calls / 0 findings; CAUS sim3 day-9 AUTHENTICATED scenario → **SKIPPED** `skipped_no_session`, no `SIM_ONBOARD_SECRET`). Bug-hunter had no live browser tool bound this run → console-error inspection + all 12 authed dashboard pages uncovered (public/API-shell coverage only, honestly flagged). Legal regression scan CLEAN (0 BUY/SELL/HOLD/매수/매도; DisclaimerBanner mount present; naked-ticker + AI-Coach greps clean).

- [ ] 🟥 **P1 (🔁 recurring 06-27 / 06-30 / 07-01 / 07-02 — 4th+ consecutive day, ESCALATE) — prod US 주식·인덱스 데이터 전면 불능.** Re-confirmed by curl 07-02: public unauthenticated `GET /api/public/market-snapshot` still returns `^GSPC` (S&P 500) / `^IXIC` (Nasdaq 100) / `^VIX` all `value:null, observed_at:null` while KR (`^KS11` 8476.48, `^KQ11` 916.18) + `USDKRW` 1541.85 populate (stale ~17h but real). Bug-hunter re-confirmed `/api/lookup/AAPL|NVDA|TSLA|MSFT` → 404, KR 200. Every visitor's first impression = 3 blank US headline indices. Root cause chain unchanged: `fetcher.quick_lookup` Alpaca(OFF)→`fmp.get_quote` (`services/data/fmp.py:299-301` returns None when key missing/quota)→None→404. Bug-hunter notes commit `7e716091` (soft-limit→250/day) is a **plausible-but-not-confirmed** trigger — the in-process budget counter resets every 24h so it alone wouldn't explain a persistent 6-day outage → more likely **invalid/expired/missing prod `FMP_API_KEY`**. **CEO/infra action (NOT a code fix, and detection-only): verify Railway `FMP_API_KEY` validity + remaining quota.** ⚠️ separately `research_fmp_replacement.md`: FMP free tier likely violates commercial-display terms — key restoration ≠ license compliance (P0 open). Files: `services/data/fetcher.py:362-410`, `services/data/fmp.py:299-301`, `routes/market.py`.
  - sub (unchanged): market-snapshot `cache_warm:true` while US values null → misleading freshness. Fix alongside: don't count null as cache-warm.
- _Re-confirmed, NOT re-escalated (see 06-30/07-01 for full detail): **P2** `morning-brief-plus` orphaned from `/sample-reports` gallery index + sitemap (`page.tsx` REPORTS array = 17 slugs, `[slug]/page.tsx` registers 18). **P2** sitemap.xml/robots.txt hardcode non-www `BASE_URL` while site canonicalizes to `www.` (SEO-only). **P2** `/api/beta-auth → 500` + gate OPEN (intentional Stage-0 demo). DRAFT ToS/Privacy banners (external-lawyer gate, `SHIP_BLOCKERS.md`)._
- _**🔁 Recurring systemic gap (CEO action, 6th+ repeat):** restore `SIM_ONBOARD_SECRET` to cron env — without it authed CAUS = SKIPPED and 12 auth-gated dashboard/detail pages stay unverified every run. Railway Variables holds the matching HMAC._

## 2026-07-01 (daily-sweep, prod) — DETECTION-ONLY (uncommitted user work: `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js`, submodule `.claude/skills/ui-ux-pro-max`)

**P0=0. No auto-fix (detection-only run).** Hermetic sweeps clean (virtual 991 calls / 0 findings; CAUS sim2 day-8 PUBLIC scenario ran 0/0). Legal scan CLEAN (BUY/SELL/HOLD/매수/매도 = 0, DisclaimerBanner present, forbidden_terms 181 lines un-rendered). Naked-ticker tab title now FIXED (`16eff2ce`).

- [ ] 🟥 **P1 (🔁 recurring 06-27 / 06-30 / 07-01, escalate) — prod US 주식·인덱스 데이터 전면 불능.** All US lookups 404 (`/api/lookup/AAPL|NVDA|TSLA|MSFT|GOOGL|SPY` → `404 not found`), KR normal (`005930.KS` → 200 삼성전자 ₩334,000, curl 07-01). **Public unauthenticated** `/api/public/market-snapshot` → S&P 500 / Nasdaq 100 / VIX all `value:null, observed_at:null` (re-confirmed 07-01, identical to 06-30) → every visitor's first impression has 3 blank US headline indices. Root cause: prod FMP source returning nothing for US — `fetcher.quick_lookup` chain Alpaca(OFF)→`fmp.get_quote` (`services/data/fmp.py:299-301` returns None when key missing)→`get_info`→None→404. Most likely **FMP free-tier 250/day quota exhausted** (default set by commit `7e716091`) OR invalid/missing prod `FMP_API_KEY`. ⚠️ correction vs bug-hunter: `/api/health missing_recommended:1` does **NOT** corroborate FMP — CLAUDE.md documents that as the pre-existing SENDGRID gap. **CEO/infra action** (not a code fix, detection-only): check Railway `FMP_API_KEY` validity + remaining quota. ⚠️ separately `research_fmp_replacement.md`: FMP free tier likely violates commercial-display terms — key/quota restoration ≠ license compliance (P0 open). Files: `services/data/fetcher.py:362-410`, `services/data/fmp.py:299-301`, `routes/market.py:718,1174-1230,1533`.
  - sub: market-snapshot `cache_warm:true` counts null US values as "warm" + all items `is_stale:true` → misleading freshness signal. Fix alongside: don't count null as cache-warm.
- [ ] **P2 (NEW) — www canonical drift (SEO).** prod canonical = `https://www.pivoxquant.com` (apex 307→www) but `frontend/src/app/sitemap.ts:3` and `frontend/src/app/robots.ts:3` hardcode non-www `https://pivoxquant.com` → `/sitemap.xml <loc>` + `/robots.txt Host:/Sitemap:` all emit non-www → GSC indexing split / canonical signal dilution. Fix: both `BASE_URL` → `https://www.pivoxquant.com`. Functional impact none.
- _Re-confirmed, NOT re-escalated: P2 `morning-brief-plus` missing from `/sample-reports` index (06-30, unchanged — `[slug]/page.tsx:40` registered, `page.tsx` REPORTS array still 17 slugs). P2 `/api/beta-auth → 500` + gate OPEN (intentional Stage-0 demo per `b6588089`/`9015b55d`/`31b051fb`; dead route + daily CAUS warning only — CEO call: retire route or re-enable gate). DRAFT ToS/Privacy banners (external-lawyer gate, `SHIP_BLOCKERS.md`)._
- _**🔁 Recurring systemic gap (CEO action, repeat):** restore `SIM_ONBOARD_SECRET` to cron env — without it authed CAUS = SKIPPED and 12 auth-gated dashboard/detail pages stay unverified every run (post-auth UI: NaN/undefined, console errors, mobile layout). Railway Variables holds the matching HMAC._

## 2026-06-30 (daily-sweep, prod) — DETECTION-ONLY (uncommitted user work: `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/.env.production`, `frontend/public/sw.js`, `.claude/launch.json`)

**P0=0. No auto-fix (detection-only run).** Hermetic sweeps clean (virtual 991 calls / 0 findings; CAUS sim1 day-7 SKIPPED — no `SIM_ONBOARD_SECRET`). Bug-hunter authed-page sweep BLOCKED (same secret gap → public-only coverage). Legal regression scan CLEAN (0 BUY/SELL/HOLD/매수/매도; DisclaimerBanner present).

### NEW — verified by direct curl
- [ ] **P1 (NEW) — Public landing ticker shows `null` for all 3 US indices (S&P 500 / Nasdaq / VIX).** `GET https://www.pivoxquant.com/api/public/market-snapshot` returns `^GSPC`, `^IXIC`, `^VIX` all `value=null, observed_at=null, is_stale=true`, while KR indices (`^KS11` 8286.3, `^KQ11` 909.14) and `USDKRW` 1536.79 populate with real (if ~17h-stale) values. This is a **public unauthenticated endpoint** → NOT a demo-mode artifact; the very first impression for every visitor renders 3 blank US headline indices. Confidence on the null fact = **100% (curl, 2026-06-30)**; root-cause hypothesis (bug-hunter): `_indices_cache["us_v2"]` never warmed after cold deploy + no APScheduler job warms the FMP US-index fetch (`routes/market.py:1509-1659`, `services/scheduler/cron_jobs.py`). **Plausibly the same prod US-data gap as the 06-27 `/api/lookup` US-404 finding** (FMP US source returning nothing — cf. local hermetic `FMP_API_KEY not set` error; prod FMP key state unverifiable from here). **Before fix:** confirm (a) prod `FMP_API_KEY` set & US index fetch working, (b) whether a cache-warm job should be added vs the US source itself is down. Also minor: `^IXIC` is the Nasdaq **Composite** ticker but labeled "Nasdaq 100".
- [ ] **P2 (NEW) — `morning-brief-plus` template orphaned from `/sample-reports` index.** The dynamic route `sample-reports/[slug]/page.tsx:40` registers 18 templates incl. `morning-brief-plus`, but the index `sample-reports/page.tsx` REPORTS array lists only **17 slugs** (weekly-memo … year-end-letter) — `morning-brief-plus` absent. Reachable by direct URL, but unlinked from the gallery (so effectively invisible to visitors). Confirmed via grep 2026-06-30. Fix: add the entry to the index REPORTS array + verify sample data wiring.

### Known/tracked — re-confirmed, NOT re-escalated
- [x] ~~**P2 (recurring, since 2026-06-25) — `/api/beta-auth` → 500 + sitewide beta gate OPEN**~~ **CLOSED 2026-09-04 — 라우트 삭제(게이트 폐기).** (`BETA_PASSWORD` unset on Vercel; free-launch posture, no user blocked). Bug-hunter re-flagged as "P1 #1"; our standing diagnosis holds it at P2 (dead 500 route + daily CAUS auth warning only). CEO call: set `BETA_PASSWORD=<value — see Vercel env / password manager>` on Vercel or retire the dead route.
- [ ] **(external blocker, not a code bug) — Draft ToS/Privacy live with "변호사 검토 대기 초안 … 게시 금지" banners on `/terms` & `/privacy`**, linked from login/signup consent. Known SHIP_BLOCKER awaiting external lawyer sign-off (핀테크 상담소). No new action; tracked in `SHIP_BLOCKERS.md`.

### 🔁 Recurring systemic gap (meta) — CEO action, 5th+ repeat
- _**Restore `SIM_ONBOARD_SECRET` to the cron env.** Without it, authed CAUS = SKIPPED and the bug-hunter can only reach public/demo prod state — leaving the 16 auth-gated pages unverified every run. Railway Variables holds the matching HMAC; `/tmp/sim-onboard-secret.txt` lost to reboot._

## 2026-06-12 (daily-sweep, prod)

- [ ] **P1-1 — Score `N/100` renders on detail pages.** `DetailHero.tsx:575-579` + `PillarGrid.tsx` render headline + 4 pillar scores live on prod; backend `/api/signals/*` still returns `score/tech_score/fund_score/news_score/quant_score`. **DECISION NEEDED**: is this a divergence from 점수화 폐기 (✅확정, "점수화 비활성 dormant 보존"), or an intentionally-retained factor display distinct from the abolished AI-currency score? Resolve scope in DECISIONS.md before any fix. If divergence → gate render + stop backend emitting fields.
- [ ] **P1-2 — Score `N/100` in alert history (14 instances).** Legacy DB alert `message` strings pre-abolition. Needs one-time DB UPDATE scrub + ensure alert-generation path no longer embeds scores. (e.g. "삼성전자 (005930.KS) — Score 60/100")
- [ ] **P1-3 — Naked `.KS`/`.KQ` in alert history (11 instances).** Legacy DB alert strings, violates `feedback_ticker_display.md`. Same DB-scrub + normalize alert-gen path. (e.g. "삼성전자 (005930.KS)")
- [ ] **P1-4 — Browser tab title includes `.KS`** (known FINDING-013). `detail/[ticker]/layout.tsx:14,28-29` keeps raw suffix in tab title "삼성전자 005930.KS · Equity Dossier". Strip suffix for KR.
- [ ] **P1-5 — Bare numeric KR codes as secondary IDs** on Portfolio / Signals list / AI dropdown / Watchlist SYMBOL column. Borderline P1/P2 — CEO taste call on whether bare `005930`-style codes are acceptable as the symbol identifier (NAME column already uses `displayTicker()` correctly).

## 2026-06-13 (daily-sweep, prod)

- [ ] **P1-A (NEW) — Discover KR Movers "losers" returns reversed gainers (all-positive %).** `routes/discover.py:272` — `losers = list(reversed(filtered))[:10]` where `filtered` is sorted `change_pct` descending. Reversed slice = smallest-gain end, NOT actual negative performers; when KR pool is all-up or small (<20), "하락 종목" shows positive-% stocks overlapping the gainers list. Gate `if len(gainers) >= 3 and len(losers) >= 3` (line 277) always passes since both derive from same pool → no fallback. **Fix**: losers = filter `change_pct < 0` sorted ascending (largest loss first); if fewer than N negatives, show "no decliners today" state. Regression: `tests/test_discover_movers.py` assert every loser `change_pct < 0`. Confidence 100% (root cause confirmed in source).
- _Note: P1-B..E from today's sweep map to existing P1-1..P1-5 above (score N/100, naked tickers, tab title, alert strings) — confirmed still present, not re-listed._

## 2026-06-15 (daily-sweep, prod)

- _No new P1s. P1-A (discover.py:273) re-verified still open. Severity clarification: `list(reversed(filtered))[:10]` **does** correctly return the lowest movers (not a gainer/loser value inversion as first worded) — the real defect is the "하락 종목" label applied to positive-% stocks when the KR pool has no decliners (all-green / <20 universe). Mild semantic mislabel; fix as previously described (filter `change_pct < 0`, "no decliners today" empty state). P1-1..P1-5 unchanged. Hermetic sweeps clean (virtual 991 calls/0 findings, CAUS 0/0). 18 authed dashboard/detail pages still unsweepable on prod (no Railway `DEV_LOGIN_SECRET`) — recurring coverage gap._

## 2026-06-16 (daily-sweep, prod — detection-only)

- _No new P1s. Detection-only run (uncommitted submodule `.claude/skills/ui-ux-pro-max` tripped git guard). Hermetic sweeps clean (virtual 991 calls/0 findings). CAUS sim7 day-3 raised a P1 on `/risk` ("no 7-Layer keywords") that is a **FALSE POSITIVE** — `SIM_ONBOARD_SECRET` unset → scenario ran unauthenticated; `/risk` is an authed `(dashboard)` route, verified `307 → www`, 238-char "Redirecting..." shell. Recurring coverage gap, not a regression._
- _**Refinement to P1-1/P1-2 (score /100):** `PillarGrid.tsx:25` uses `const safe = Number.isFinite(score) ? clamp(score) : 0` → renders **`"0 / 100"`** for missing scores (looks like a real low score), which is **worse** than `DetailHero.tsx:579` rendering `"— / 100"`. When the DECISIONS.md score-display scope call resolves, fix PillarGrid to fall back to `"—"` not `0`._
- _P1-A (discover losers mislabel) + P1-4 (detail tab title `.KS`) + P1-5 (bare KR codes) all unchanged. CEO actions outstanding: (1) restore `SIM_ONBOARD_SECRET` to cron env to unlock authed CAUS coverage; (2) DECISIONS.md scope call on score `/100` before P1-1 fix._

## 2026-06-17 (daily-sweep, prod — detection-only)

- [ ] 🟥 **P0-DEPLOY (NEW — top priority) — prod/main is 59 commits behind `feat/mirror-home-unified`, and the gap includes 2 LIVE P0 privacy fixes.** Prod runs `15f3d211` (PR #508). `git rev-list --count 15f3d211..HEAD` = **59**. Two privacy defects are **live in prod right now** but **already fixed locally at `c05e4915`** (dated 2026-06-10, verified NOT an ancestor of `15f3d211`):
    - **(P0-1)** `frontend/public/sw.js` — service-worker `STALE_WHILE_REVALIDATE_CONFIG` prefix-matches `/api/profile`, so it caches `/api/profile/export` (the full PIPA §35 personal-data dump) for up to 60 min.
    - **(P0-2)** `frontend/src/lib/auth.tsx` — OAuth login does not clear the SW API cache → on a shared device User B can see User A's cached profile data for up to 60 min.
    - **Action = CEO deploy** (merge/push is CEO's separate-session job per `feedback_push_workflow`). No code fix to make — the fixes exist; they must reach prod. The same branch also carries the discover/portfolio-NAV/risk-NaN/alert-$0/artifact-$nan fixes (`7c81f078 2610c824 08c51390 32a01298 30150213`), all verified local-only (not ancestors of `15f3d211`). Deploying the branch closes P1-A and most P1-1..P1-5 simultaneously.
- [ ] **P1-10 (legal-review, not code-defect) — DRAFT / 「초안(Draft)」 framing renders on the LIVE public `/privacy` (and `/terms`).** `privacy/page.tsx` renders `src/content/privacy-ko.md` verbatim and that markdown still carries v2.0-DRAFT language. Per memory the legal docs are *intentionally* DRAFT pending the external-lawyer gate — so this is a **CEO/legal decision** (hide DRAFT wording on public surfaces until sign-off, or keep it transparent), not an autofix. (bug-hunter flagged P1; reclassified here.)
- _P2 (count only): (a) `features/*` copy says "seventeen artifacts"/"17 artifacts" (6 strings) while memory references 18–19 — confirm true catalogue count before any copy edit. (b) Market ticker strip shows zeros/STALE outside KR+US market hours — likely expected off-hours behavior, unverified as a defect._
- _Hermetic sweeps clean: virtual 991 calls / 0 findings; CAUS sim8 day-4 0/0. P1-1..P1-5 + P1-A all still live in prod (their fixes are part of the 59-commit undeployed gap). Authed dashboard/detail pages still unsweepable on prod (no `SIM_ONBOARD_SECRET`) — recurring coverage gap._

## 2026-06-20 (daily-sweep, prod — detection-only)

- [ ] **P1-DEMO (NEW) — Recruiter demo renders all buy trades as "Sold" (side format mismatch).** `frontend/src/lib/demo.ts:438-444` `DEMO_TRADES` uses lowercase wire format `side: "buy"/"sell"`, but `frontend/src/components/portfolio/activity-paper.tsx:139` checks `t.side === "Bought"` (Title case). With `frontend/.env.production:12 NEXT_PUBLIC_PORTFOLIO_V2=false` (prod default), the V1 portfolio page uses `ActivityPaper` → all 5 demo buys display as sells (red, minus sign). The V2 transactions block handles lowercase correctly, but V2 is OFF in prod. Demo-only (does not affect real-user data path), but visible on the recruiter-facing demo. **Fix options**: (a) normalize `DEMO_TRADES` side to `"Bought"/"Sold"`, (b) add `.toLowerCase()` compare in `activity-paper.tsx`, or (c) set `PORTFOLIO_V2=true` in Vercel demo env. Confidence 100% (format mismatch verified in source). Verified via static code inspection (Chrome MCP not connected in scheduled context).
- _**P0-DEPLOY (06-17) → RESOLVED.** Prod SHA is now `30e31e52`; privacy fix `c05e4915` (sw.js `/api/profile/export` cache exclusion + OAuth cache clear) is confirmed an ancestor of `30e31e52` (`git merge-base --is-ancestor` = true). The 59-commit deploy gap has been deployed. Local committed `sw.js` carries the export-exclusion at line 49. The current working-tree `sw.js` change is a benign `CACHE_VERSION` build bump (`pq-build-b5834882 → pq-build-2b0acfc8`), not a regression._
- _P2 (count only): (a) `demo.ts` canned news headline "애널리스트, …목표가 상향 조정" contains 목표가 — `forbidden_terms.py` scope is AI artifact copy, not journalism headlines, so not a CI violation; gray-area only. (b) prod health `missing_recommended: 1` (SENDGRID_WEBHOOK_PUBLIC_KEY) — pre-existing, documented in CLAUDE.md._
- _Hermetic virtual sweep clean (991 calls / 0 findings). CAUS rotated to **authed** sim1 day-7 (/simulator/what-if) → **SKIPPED** (skipped_no_session; `SIM_ONBOARD_SECRET` unset). Authed CAUS coverage still blocked — CEO action: restore `SIM_ONBOARD_SECRET` to cron env. Git guard tripped (uncommitted `SHIP_BLOCKERS.md` / `sw.js` / submodule) → detection-only, no fixes/commits._

## 2026-06-22 (daily-sweep, prod — detection-only)

- [ ] **P2-PRETRADE (NEW) — Naked `005930.KS` in /pre-trade ticker placeholder.** `frontend/src/app/(dashboard)/pre-trade/page.tsx:188` `placeholder="AAPL · 005930.KS"` — hardcoded naked suffix, violates `feedback_ticker_display.md` (CEO-flagged 3+). Trivial fix: `placeholder="AAPL · 005930"`. Confidence 100% (source). Borderline P2/P1 (naked-ticker is a CEO hot-button) — routed P2 as it's a placeholder string, not live data.
- _**bug-hunter "P0" (KR movers US data) + "P1 #2" (KR indices US data) + "P1 #3" (billing 200 ok:true) = ALL FALSE POSITIVES.** Hunter ran in demo mode (`demo@pivoxquant.com` dev-login → `NEXT_PUBLIC_DEMO_MODE=1`). Evidence served by `frontend/src/lib/demo.ts` fixtures (`:361-363` movers `region:"us"` static; `ok:true` billing stub), NOT the backend. Real `routes/discover.py:246/294/318` is region-keyed + returns 503 for empty KR (never US data); `routes/market.py:1367` region-keyed; `routes/billing.py:116` has STRIPE 503 gate. Prod runs this code (PR #522). Not bugs — see `BUG_SWEEP_2026-06-22.md`._
- _Still-open from prior sweeps re-confirmed present (not re-fixed, detection-only): **P1-4** naked `.KS` in detail `<title>` (`detail/[ticker]/layout.tsx:29`); **#6** raw `^GSPC`/`^IXIC`/`^KS11` index codes in `market/overview-paper.tsx:168/340` (P2 cosmetic). P1-DEMO (06-20 side-format) unchanged._
- _Hermetic sweeps clean (virtual 991 calls / 0 findings). CAUS sim3 day-9 SKIPPED (skipped_no_session). PDF matrix skipped (Monday). Local HEAD `9015b55d` is 1 commit BEHIND `origin/main` `0cc8fca2` (prod) — pull the PR #522 merge commit. Authed CAUS still blocked on `SIM_ONBOARD_SECRET`._

## 2026-06-23 (daily-sweep, prod — detection-only)

- _**bug-hunter "P0-1" (/market KR tab US data) + "P0-2" (/discover KR movers US-as-KRW) + "P1-2" (signals/risk 5-day stale) = ALL DEMO-MODE FALSE POSITIVES — identical recurrence of the 2026-06-22 trap.** Hunter ran against prod in demo mode (`demo@pivoxquant.com` → `NEXT_PUBLIC_DEMO_MODE=1`), so all dynamic data is served by `frontend/src/lib/demo.ts` fixtures, NOT the backend: `demo.ts:361` movers `region:"us"` static; `demo.ts:187-190` risk fixtures hardcode `observed_at_kst:"2026-06-18T16:30:00+09:00"` (the "5-day stale" timestamp is a frozen fixture string, not real staleness). Real backend is correct: `routes/market.py:1195-1211` returns US ETF proxies for `us` / KR indices for `kr` per region; `routes/discover.py:246` cache key is `movers:{region}:{user.id}` (region-keyed, per-user) and returns 503 (never US data) for empty KR. Prod runs this code (PR #522, sha `0cc8fca2`). Not bugs — see `BUG_SWEEP_2026-06-23.md`._
- _**P1-3 (watchlist 52W "–") + P1-4 (watchlist OBSERVATION PENDING never clears) = also demo-mode fixture artifacts**, not real backend defects (same demo.ts source). Needs authed (non-demo) verification before treating as real — blocked on the coverage gap below._
- [ ] **Still-open REAL item re-confirmed (not re-fixed, detection-only): P1-4 (prior) — naked `.KS` in detail `<title>`** (`frontend/src/app/(dashboard)/detail/[ticker]/layout.tsx:29` uses raw `upper` = `005930.KS`). Frontend code (not demo data), genuinely live. Trivial fix: strip suffix for KR in title construction. Already tracked since 2026-06-12 P1-4 / 06-17 / 06-22._
- _🔁 **Recurring systemic gap (meta) — CEO action: restore `SIM_ONBOARD_SECRET` to the cron env.** Without it, authed CAUS is SKIPPED and the only reachable prod state for the bug-hunter is demo mode, whose `demo.ts` fixtures make every dynamic-data finding a false positive (now 2 consecutive runs wasted this way). Restoring the secret unlocks authed coverage and stops the FP churn. (Railway Variables holds the matching HMAC; `/tmp/sim-onboard-secret.txt` was lost to reboot.)_
- _Hermetic sweeps clean (virtual 991 calls / 0 findings). CAUS sim4 day-0 raised 1 "P0" (`/api/me` 403, issue #523) = the `SIM_ONBOARD_SECRET`-unset harness gap (sim-onboard mint can't auth), NOT a product bug. PDF matrix skipped (Tuesday). Git guard tripped (uncommitted `SHIP_BLOCKERS.md` / `sw.js` build-version bump / submodule `ui-ux-pro-max`) → detection-only, no fixes/commits._

## 2026-06-24 (daily-sweep, prod) — DETECTION-ONLY (uncommitted user work present: SHIP_BLOCKERS.md, sw.js, ui-ux-pro-max submodule)

### 🟥 P0 — ESCALATE TO CEO (not auto-fixed: detection-only run)
- [ ] **P0-1 (NEW) — /discover "Today's Movers — Korea" shows US stocks with fabricated KRW prices.** KR Markets section renders TSLA/AVGO/NVDA/LLY/UNH as Korean movers labeled "KRW 413 / KRW 1,821 / KRW 183" (US dollar amounts rounded + mislabeled KRW). **표시광고 risk** (misleading display of US equities as KR-priced). Root cause: `/api/discover/movers?region=kr` ignores `region` param, always returns `region:"us"` data; frontend `fmtMoverPrice(r.price, true)` hardcodes `isKr=true` → `KRW ${Math.round(price)}`. Files: `frontend/src/app/(dashboard)/discover/page.tsx:131,211-214,231-242` + backend `routes/discover.py` movers endpoint. **Supersedes/compounds existing P1-A** (region param ignored) — escalate to P0 because user-visible fabricated KRW prices on US tickers. Confidence: high (independent bug-hunter visual + endpoint trace).

### P1 (accumulated — CEO review)
- [ ] **P1 (NEW) — 6-day stale data + raw ISO timestamp leaked to users.** Detail pages show "관측 6/18/2026" (today=6/24); risk board renders verbatim `"Seven layers observed at 2026-06-18T16:30:00+09:00."` No staleness indicator + raw ISO string. May indicate **stalled data-refresh job** (worth ops check). File: `frontend/src/components/risk/v2/risk-hero-v2.tsx:40-41` + backend refresh pipeline.
- [ ] **P1 (NEW) — Pre-Trade input placeholder exposes naked `.KS`.** `<input placeholder="AAPL · 005930.KS">` violates ticker-display rule. File: `frontend/src/app/(dashboard)/pre-trade/page.tsx:188`.
- [ ] **P1 (NEW) — /discover Quant Engine Scan permanently stuck "Loading live quant scan…".** `/api/discover/quant-scan` returns empty `{}` (200); frontend SWR treats `{}` as still-loading instead of empty-state. File: `frontend/src/app/(dashboard)/discover/page.tsx` quant-scan SWR.
- [ ] **P1 (NEW) — /watchlist 52W Range column "—" for all rows.** `/api/watchlist` omits `week_52_high`/`week_52_low`. Backend watchlist endpoint.
- [x] _P1 (DUP) — Detail `<title>` tag exposes `.KS` ("삼성전자 005930.KS · Equity Dossier"). = existing 2026-06-12 P1-4, still open._

### Observations / ops notes (not P0/P1 code bugs)
- ⚠️ **CAUS beta-gate auth returned 500** ("beta-gate auth non-200 (500) — scenarios may short-circuit at the gate"). Vercel beta-gate edge function may be erroring; api-sentinel 03:51 shows **backend** health ok (db ok, ver eda2d6b8), so likely isolated to the Vercel password-gate fn. Worth a CEO check of the beta-gate function logs.
- ℹ️ **CAUS P0 `['매수']` on /signals = known false-positive.** Substring of `순매수` (net-buy, observational market-data figure), NOT a trade directive. Confirmed by bug-hunter visual scan (POSITIVE/NEUTRAL/NEGATIVE signals only, no BUY/SELL/HOLD). Auto-fix correctly escalated as contested-interpretation. No code change warranted (per `feedback_legal_filter_design` — don't over-scrub neutral prose).

## 2026-06-25 (daily-sweep, prod) — DETECTION-ONLY (uncommitted user work present: SHIP_BLOCKERS.md, frontend/public/sw.js, ui-ux-pro-max submodule)

**P0=0. No auto-fix dispatched (detection-only + P0=0).**

### Root-caused (NEW diagnosis) — was an "observation" on 06-24, now traced
- [ ] **P2 — `/api/beta-auth` returns 500 `{"error":"Beta gate is not configured"}` on www.pivoxquant.com.** This is the source of the recurring CAUS "beta-gate auth non-200 (500)" warning (06-24 flagged it but didn't trace it). Root cause: the Vercel beta-auth route can't read `BETA_PASSWORD` env (unset/misnamed on the Vercel prod deployment). **NON-BLOCKING**: the sitewide gate is OPEN — `/home /portfolio /market /signals` all return 200 unauthed and serve the real app (free-launch posture), so no user is blocked; the 500 only breaks CAUS's auth helper. Effect = dead route + a daily CAUS warning. Fix options: (a) set `BETA_PASSWORD` on Vercel so the route 200s, or (b) remove the now-unused beta-auth route entirely if the gate is intentionally retired. CEO call. Backend (Railway) health is clean (db ok, ver eda2d6b8).

### Re-confirmed STILL-OPEN (not re-fixed, detection-only) — broaden prior entry
- [ ] **P1/P2 (recurring, now broadened) — naked `005930.KS` in input placeholders is in 5 files, not 1.** Prior sweeps tracked only `pre-trade/page.tsx:188`. Full grep today: `frontend/src/app/(dashboard)/pre-trade/page.tsx:188`, `frontend/src/components/growth/onboarding-brag-card.tsx:188`, `frontend/src/components/portfolio/add-position-modal.tsx:115`, `frontend/src/components/portfolio/v2/add-position-modal-v2.tsx:393`, `frontend/src/components/watchlist/add-symbol-modal.tsx:175`. Per 철저한_수정 (thorough-fix), if changed, change all 5. **Borderline**: these are input-format hints — `.KS` IS the suffix a user must type for KR stocks, so the placeholder teaches valid input, unlike the display-policy violation (showing a code where a name belongs). Recommend CEO decide whether to swap to `"AAPL · 삼성전자"` or leave as functional input hints. Confidence 100% (source-grep).
- [ ] **P1 (DUP, still open) — detail `<title>` exposes `.KS`** (`frontend/src/app/(dashboard)/detail/[ticker]/layout.tsx:29`). Tracked since 06-12 P1-4. Real frontend code, not demo data.

### Demo-mode false-positive guard (recurring trap, 3rd+ run)
- _bug-hunter again authed as `demo@pivoxquant.com` → `NEXT_PUBLIC_DEMO_MODE=1`, so its data findings come from `frontend/src/lib/demo.ts` fixtures, not the backend. This run's **P2 "watchlist 52W Range = –"** and **P2 "signals detail API omits is_stale"** fall in this bucket — same demo-fixture artifacts flagged 06-23/06-24, NOT confirmed backend defects. The `is_stale`-missing-on-`/api/signals/<ticker>` (vs present on list route) is a plausible real API-shape inconsistency but is P2 and needs non-demo verification. No new real backend bug surfaced._
- _🔁 **CEO action (still outstanding, 3rd repeat) — restore `SIM_ONBOARD_SECRET` to the cron env.** Without it, authed CAUS = SKIPPED and the bug-hunter's only reachable prod state is demo mode, whose fixtures churn false positives. Railway Variables holds the matching HMAC; `/tmp/sim-onboard-secret.txt` lost to reboot._

## 2026-06-27 (daily-sweep, prod) — DETECTION-ONLY (uncommitted user work present: `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/public/sw.js`, `ui-ux-pro-max` submodule)

**P0=0 (no NEW P0). No auto-fix dispatched (detection-only run).** Hermetic sweeps clean: virtual 991 calls / 0 findings; CAUS sim8 day-4 "ran" 0/0 (the beta-gate 500 warning is the known P2 below — gate is OPEN so public scenarios still loaded the real app). Prod backend health ok (db ok, ver `8f97812bbb77`).

### NEW — verified
- [ ] **P1 (NEW) — `/api/lookup` 404s ALL US tickers; KR works.** Direct curl against Railway prod: `/api/lookup/AAPL`, `/NVDA`, `/MSFT` → `404 {"error":"Ticker '…' not found","ok":false}`; `/api/lookup/005930.KS` → `200`. Real US-only asymmetry. Bug-hunter's root-cause (Alpaca-off + FMP fallback → `quick_lookup()` None, `services/data/fetcher.py:362-393`) is **plausible but unconfirmed** — FMP key state not directly checkable, and whether the live frontend uses `/api/lookup` for US (viral search vs core detail flow) is also unconfirmed. **Before fix:** confirm (a) is FMP_API_KEY set on Railway? (b) does the US detail page actually render via a different working endpoint (i.e. is `/api/lookup` a legacy/search-only path)? Confidence on the 404 fact = 100% (curl); on user impact = unverified.

### Strengthening EXISTING entry
- [ ] **P1 (WORSENING — first logged 2026-06-24) — signal/risk data still frozen at `2026-06-18`, now 9 days stale.** The "관측 6/18/2026" issue has NOT advanced across the 06-24 → 06-27 sweeps — the date is stuck at 2026-06-18, which upgrades this from "slow cadence?" to **strong evidence of a stalled refresh pipeline**. (Could not reproduce via curl — `/api/signals/*` → `SESSION_EXPIRED`; evidence = bug-hunter authed read + 9-day non-advancement.) Worth an **ops check of the APScheduler signal/data-refresh job on Railway** (is the job firing? erroring silently? or is the staleness a side effect of prod being 59 commits behind per 06-17 P0-DEPLOY?). Raised priority given persistence.

### Dismissed — FALSE POSITIVE (do not re-open)
- ❌ **bug-hunter "KIS prices 2×–4× wrong (VTS paper data)" — DISMISSED.** Prod 삼성전자 = ₩339,500 matches the documented, 4-way-cross-verified KR re-rate (`memory/project_kospi_rerate_real.md`: 삼성 ≈ ₩308k is REAL). The claimed "correct ₩84,300" is the discredited pre-re-rate price the memory explicitly tells bug hunters to stop flagging. This is the 2nd+ time this exact false positive has surfaced — the test-fixture remnant (2,540) keeps misleading hunters. **No bug.**

### Known P2 — still open (not re-escalated)
- [ ] **P2 (recurring, since 2026-06-25) — `/api/beta-auth` → 500 "Beta gate is not configured" + sitewide beta gate OPEN.** `BETA_PASSWORD` unset on Vercel prod → `middleware.ts:128` skips the gate entirely → www `/ /home /portfolio /beta-gate` all 200 unauthed serving the real app. Consistent with free-launch posture; **no user blocked**, so non-blocking. Effect = dead 500 route + daily CAUS auth warning. CEO call: (a) set `BETA_PASSWORD` on Vercel to restore the gate, or (b) remove the now-unused beta-auth route if the gate is intentionally retired. (Re-confirmed present today; identical to 06-25 diagnosis.)

## 2026-06-29 (daily-sweep, prod) — DETECTION-ONLY (uncommitted user work present: `.gitignore`, `SHIP_BLOCKERS.md`, `frontend/public/sw.js`, `ui-ux-pro-max` submodule)

**P0=0 (no NEW P0). No NEW real bug. No auto-fix dispatched (detection-only run).** Hermetic sweeps clean: virtual 991 calls / 0 findings; CAUS sim10 day-6 (public `/pricing`) "ran" 1 P1 = demo-mode/beta-gate artifact (see below). Railway backend health OK (db ok, ver `8f97812bbb77`). Legal regression scan CLEAN (0 BUY/SELL/HOLD/매수/매도 leaks; DisclaimerBanner present).

### ✅ Status change — long-tracked P1-4 (detail `<title>` naked `.KS`) is FIXED in code, pending deploy
- The detail tab-title naked-`.KS` defect (tracked since **2026-06-12 P1-4**, re-confirmed 06-17/06-22/06-23/06-24/06-25) is now **fixed at commit `16eff2ce`** ("fix(detail): strip .KS/.KQ from tab `<title>`"), verified an ancestor of local HEAD `5491b0a6`. `layout.tsx:31` now uses `normalizeTicker(upper)` → "삼성전자 005930 · Equity Dossier". **BUT not yet on `origin/main`/prod** (`git merge-base --is-ancestor 16eff2ce origin/main` = false; the fix lives on branch `fix/email-provider-retry`, which is 3-ahead / 6-behind main). **CEO action: merge `16eff2ce` to main + deploy Vercel** to close it on prod (merge/push is CEO's separate-session job per `feedback_push_workflow`).

### Demo-mode false-positive guard (recurring trap — bug-hunter authed `demo@pivoxquant.com` → `NEXT_PUBLIC_DEMO_MODE=1`, prod env set by commit `31b051fb` 2026-06-26)
- _bug-hunter's **P1-1 (billing buttons silent-fail)**, **P1-2 (Korea market tab infinite loading)**, and **P2 (demo data 11 days stale, fixtures dated 2026-06-18)** are all **demo-fixture artifacts**, NOT backend defects — served by `frontend/src/lib/demo.ts` (`:34` demo user forced `subscription_tier:"premium"` → billing buttons render then no-op via the `:690` POST catch-all; `/api/market/korea` absent from fixtures → `{}` → infinite load; portfolio/signals fixtures frozen at `2026-06-18`). Same trap as 06-22→06-27. Real backend (Railway, ver `8f97812b`) is healthy and region-keyed._
- _**Reframes the 06-24/06-27 "stalled refresh pipeline" escalation:** the "9-day / now 11-day stale 2026-06-18" timestamp the bug-hunter keeps reading is the **frozen demo fixture string**, not a real stalled APScheduler job — because in demo mode every data read comes from `demo.ts`, not the backend. The real refresh pipeline **cannot be observed via demo mode**, so the "stalled pipeline" concern is **unverifiable** (not confirmed real, not confirmed clean) without authed non-demo prod access. Downgrade the prior "strong evidence of stalled pipeline" wording → "unverifiable; likely demo-fixture artifact." A genuine ops check requires the coverage-gap fix below._
- _CAUS sim10 day-6 P1 ("`/pricing` only 0 tier names visible") = same class: public scenario hit the demo/gated frontend; not a real backend bug. Beta-gate auth 500 = known P2 below._

### Known P2 — still open (not re-escalated)
- [ ] **P2 (recurring, since 2026-06-25) — `/api/beta-auth` → 500 + sitewide beta gate OPEN.** Unchanged from 06-25/06-27 diagnosis (`BETA_PASSWORD` unset on Vercel; gate OPEN per free-launch posture; no user blocked). CEO call: set `BETA_PASSWORD` or remove the dead route.
- [ ] **P1/P2 (recurring) — naked `005930.KS` in 5 input placeholders** (`pre-trade/page.tsx:188`, `onboarding-brag-card.tsx:188`, `add-position-modal.tsx:115`, `v2/add-position-modal-v2.tsx:393`, `add-symbol-modal.tsx:175`). Unchanged from 06-25. Borderline — `.KS` is the suffix a user types for KR input, so these teach valid input rather than mislabel a display. CEO taste call (swap to `"AAPL · 삼성전자"` vs leave as functional hints). Distinct from the now-fixed `<title>` display violation.

### 🔁 Recurring systemic gap (meta) — CEO action, 4th+ repeat
- _**Restore `SIM_ONBOARD_SECRET` to the cron env.** Without it, authed CAUS = SKIPPED and the bug-hunter's only reachable prod state is demo mode, whose `demo.ts` fixtures make every dynamic-data finding a false positive (now ~6 consecutive runs churned this way). Restoring it unlocks authed coverage, stops the FP churn, AND enables the genuine refresh-pipeline ops check needed to settle the "stale data" question above. Railway Variables holds the matching HMAC; `/tmp/sim-onboard-secret.txt` was lost to reboot._

## 2026-08-31 (daily-sweep) — P1 merge blocker on `refactor/prune-artifacts`

**Nothing shipping is broken.** `origin/main` still has `routes/artifacts.py`; the
break below exists only on branch `refactor/prune-artifacts` (16 commits ahead,
unmerged). Prod is separately down (Railway account deleted 2026-08-30), so none
of this is observable in prod today.

- [ ] **P1 — artefact prune (`e064118e`) deleted the backend routes but left ~8 live frontend consumers.** `routes/artifacts.py` is gone (verified: no artifact route file in `routes/`), yet `frontend/src/lib/endpoints.ts:282-313` still exports the `/api/artifacts/*` constants and these surfaces still call them:
  - `frontend/src/app/(dashboard)/reports/page.tsx:109,116` (`useArtifacts`, `useArtifactStats`) — the whole `/reports` page
  - `frontend/src/app/(dashboard)/reports/[id]/page.tsx:56` (`API.artifacts.preview`)
  - `frontend/src/components/reports/v2/latest-artifact-card.tsx:269` (`API.artifacts.download`)
  - `frontend/src/components/reports/v2/generate-artifact-cta.tsx:145,156`
  - `frontend/src/components/reports/report-preview-shell.tsx:104`
  - `frontend/src/components/home/artifact-queue.tsx:100`
  - `frontend/src/components/home/v2/companion-archive-card.tsx:36`
  - `frontend/src/components/dashboard/living-cfo-status.tsx:64`
  - `frontend/src/app/(dashboard)/detail/[ticker]/page.tsx:405`

  **Merging this branch as-is breaks `/reports` plus the home artefact queue, the
  detail related-artefacts panel, and the living-CFO status card.** Not auto-fixed:
  removing user-facing surfaces is a CEO framing call (`feedback_feature_preservation`
  requires a v1-inventory → v2-mapping table), and P1 is backlog-only by the sweep's
  own triage rule. Branch owner decides: finish the prune on the frontend too, or
  restore the backend routes.

- [ ] **P2 — dead `useMethodology` hook.** `/api/methodology` was deleted in the same
  commit. `frontend/src/lib/hooks.ts:1625` still defines `useMethodology()` and
  `endpoints.ts:473` still exports `METHODOLOGY`, but **nothing calls the hook**
  (verified) and the public `/methodology` page is a static server component, so no
  user path breaks. Dead code only — cleanup, not a bug.

### Coverage gap exposed this run
- _The virtual-user sweep reports **0 findings** while the branch's `/reports` surface
  is contract-broken, because the sweep's endpoint table has **no `/api/artifacts/*`
  coverage at all** (verified: zero artifact entries in `scripts/qa/virtual_user_sweep.py`).
  Whatever "artifact leg" commit `5f928734` added is gone. Once the artefact question is
  settled, the sweep table should regain coverage for whichever artifact endpoints survive
  — otherwise this class of break stays invisible to the nightly sweep._

### legal-guard 2026-09-04 — P1: scrub-decorator drift in `routes/behavior.py`
- Five of the six mirror routes (`/holding-mirror`, `/concentration-mirror`,
  `/profit-loss-mirror`, `/turnover-mirror`, `/averaging-down-mirror`) carry only
  `@api_auth`; `@legal_scrub_response` is on `/friction-outcome` alone (added
  2026-09-02, `routes/behavior.py:311`). Not a leak today — verified the five legacy
  payloads emit numbers plus one disclaimer literal (`behavior.py:109`), no advisory
  prose — so this is consistency drift, not a P0. Worth backfilling the decorator on
  all six so the file has one contract rather than "new routes only".


## 2026-09-04 daily-sweep (detection-only — 미커밋 사용자 작업 존재)

- [ ] 🔴 **P0 (3일째 이월) — PIPA §28-8 동의문·처리방침이 삭제된 수탁처(Railway)를 명시.**
  실제 수탁처 Render/Supabase 는 어디에도 없음. 위치: `frontend/src/app/(auth)/signup/page.tsx:599`,
  `frontend/src/content/privacy-ko.md:26,167,252`. 랜딩 §13 호스팅 표기는 이미 "Render" 로
  고쳐져 있어 **리포 내부 모순** 상태 — 부분 수정(`feedback_thorough_fixes` 위반).
  자동 수정 안 함: 법적 문안 + 수탁처(리전 포함) 확정 선행 필요 → `legal` / 변호사 큐 경유.
  미푸시 커밋 `c1f61809` 의 "PIPA cutover 게이트"와 묶을 것.

- [ ] 🟠 **P1 (3일째 이월) — 베타 게이트가 prod 에서 열려 있다.** Vercel prod env 에
  `BETA_PASSWORD` 미설정 → `middleware.ts:128` 이 게이트를 스킵. `www.pivoxquant.com` 이
  비인증 200 + 랜딩 전문 27KB 서빙(실측). `POST /api/beta-auth` → 500 "Beta gate is not
  configured". 코드 변경 불필요 — **Vercel 프로덕션 env 재설정 = CEO 액션.**

- [ ] 🟡 **P2 — 비로그인 아바타가 "게" 한 글자.** `profile-dropdown.tsx:35-46` `initials()` 가
  공백분리 이니셜(서구식)만 가정 → "게스트"에서 1글자만 남고 `"PQ"` 폴백에 도달 못 함.
  가드 1줄이면 해소.

- [ ] 🟡 **P2 — 라이브 CSP `connect-src` 가 죽은 `*.railway.app` 지시.** ⚠️ **재수정 금지** —
  미푸시 커밋 `4ca0bfd3` 에 이미 수정돼 있어 **push 시 자동 해소**된다. Render 백엔드가
  살아난 뒤에도 push 가 안 된 상태면 조용히 막히므로(CSP 위반은 콘솔에만 뜸) push 전까지 열어둔다.

### 이번 런에서 CLOSE 된 이월 항목
- ✅ P1 "`/api/artifacts/*` 계약 파손" — 프론트 프룬 완료로 해소(`reports/` 부재, `API.artifacts` 참조 0건).
- ✅ P2 "dead `useMethodology` 훅" — 제거 확인.

### 오탐 (재보고 금지)
- ❌ "Vercel 자동배포 동결 / prod 가 3커밋 뒤처짐" — **사실 아님.** prod 는 `origin/main`(`cee3d291`)과
  타임스탬프까지 정확히 일치. 해당 3커밋은 main 이 아니라 **미머지 피처 브랜치**에 있고, 로컬 main 은
  10커밋 **미푸시**(= `feedback_push_workflow` 정상 운영, `SHIP_BLOCKERS` A8). `vercel --prod` 강제
  재배포는 무의미하니 하지 말 것.


---

## 2026-09-05 (daily-sweep, prod) — DETECTION-ONLY (미커밋 사용자 작업: `.claude/skills/ui-ux-pro-max` 서브모듈 dirty)

리포트: `BUG_SWEEP_2026-09-05.md` (572줄) · 브랜치 `fix/sweep-2026-09-04` @ `c20d7643`
프로드 배포 빌드 = `main` @ `c1f61809` (실측: `www.pivoxquant.com/sw.js:25` `CACHE_VERSION="pq-build-c1f61809"`)

- [ ] 🟥 **P0 (4일째 이월, 오늘 범위 확대) — 개인정보처리방침 §6 수탁자·국외이전 표가 3중으로 틀림.**
  라이브 `/privacy` §6 이 `Railway Corp. | 미국 | DB 저장 데이터 | 백엔드 호스팅 및 데이터 저장` 으로 고지 중이고
  §9-3 은 `국외 클라우드(Railway 등)` 라고 서술. **Railway 계정은 2026-08-30 삭제됐다.**
  `grep -rn "Supabase\|Render" frontend/src/content/` → **0건.**
  ⚠️ **오늘 코디네이터가 직접 실측해 확정한 신규 사실 2건** (bug-hunter 는 "미확정"으로 남겼던 부분):
  1. **DB = Supabase 프로젝트 `pivoxquant`(ref `yjiztgummaxecriiuumt`), region `ap-northeast-2` = 서울, ACTIVE_HEALTHY**
     (Supabase MCP `list_projects` 실측) → **DB 저장은 이제 국내다. 국외이전 대상이 아니다.**
  2. **백엔드 호스팅 = Render, region `singapore`** — `render.yaml:28` 이 이미 명시:
     `region: singapore # closest Render region to KR users; Supabase DB is in ap-northeast-2 (Seoul)`
  → 따라서 현 고지는 **수탁자(Railway→Render/Supabase)·국가(미국→싱가포르)·이전범위(DB는 국외이전 없음)** 세 축 모두 오류.
  가입 시 PIPA §28-8 [필수] 동의를 **틀린 목록으로 수집 중**이며, 백엔드가 09-04 부터 라이브라 **실노출이 재개됐다**
  (어제까지는 signup 404 라 노출 0이었음 — 그 완충이 사라졌다).
  동반 수정 대상: `frontend/src/content/privacy-ko.md:26,167,252` · `app/(auth)/signup/page.tsx:57,599`
  · `lib/consents.ts:181-183` · `app/__tests__/signup-v2.test.tsx:78`(8개 카운트 테스트).
  **자동 수정 안 함**: 국외이전 범위 축소는 문안·동의 재수집 여부까지 걸리는 법적 판단 → `legal` / 변호사 큐.
  미푸시 `c1f61809` "PIPA cutover 게이트"와 반드시 묶을 것.

- [ ] 🟠 **P1 — FMP API 쿼터 소진(HTTP 429) → US 데이터 경로 전면 정지. CEO 액션(대시보드 확인) 필요.**
  `curl ".../stable/quote?symbol=SPY&apikey=<KEY>"` → 429 `{"Error Message":"Limit Reach . Please upgrade your plan…"}`
  AAPL 3회 연속 + historical 도 동일 → 분당 rate 가 아니라 **플랜 쿼터 소진/구독 다운그레이드**.
  영향: `services/fx_service.py` `services/alert.py` `services/data/{fetcher,realtime}.py` `routes/{market,portfolio}.py`
  = US 시세·히스토리·뉴스·펀더멘털 + USD/KRW d/d%. `services/data/fmp.py:106-112` 의 10분 쿨다운 덕에 **500 아닌 조용한 degradation**.
  ⚠️ `research_fmp_replacement.md` 와 결속: 무료 대체 없음(전 free tier 가 상업표출 금지)이 이미 확정 → **결제/플랜 판단은 CEO 전용**.
  미확정: Render 의 `FMP_API_KEY` 가 로컬 `.env` 키와 동일한지 확인 불가.

- [ ] 🟠 **P1 — 랜딩 히어로 티커 6칸 중 US 3칸(S&P 500 / Nasdaq 100 / VIX)이 영구 `—`.**
  2회 폴링 동일: `^GSPC/^IXIC/^VIX` 전부 `value:null, is_stale:true, observed_at:null`.
  체인 실측: `routes/market.py:753` US=ETF프록시 → `:346` 전부 None → **`:893 if out:` 라서 US 캐시가 영원히 안 채워짐**.
  업스트림 둘 다 죽음 — Alpaca `render.yaml:58-59 ALPACA_ENABLED="0"`(라이선스 사유, 의도된 OFF) + FMP 429(위 항목).
  스케줄러는 정상 가동(`app.py:1367-1375`, 60s) = 잡 문제 아님.
  ⚠️ `cache_warm:true` 가 **KR 만 warm 인데 true 로 잡혀 US 실패를 가린다** → 지표 자체가 오탐 유발.
  근본 fix = FMP 해소. 표시 fix(값 없을 때 US 행을 `—` 대신 숨김/명시)는 **비로그인 첫 화면**이라 CEO framing 권장.

- [ ] 🟠 **P1 — `/beta-gate` 가 prod 에 생존, 제출 시 HTTP 500.** (어제 P1 의 잔여분 — 성격이 바뀜)
  `/beta` → `<meta http-equiv="refresh" content="1;url=/beta-gate">` → `/beta-gate` 200 "Private Beta / 베타 비밀번호"
  → `POST /api/beta-auth` → **500** `{"error":"Beta gate is not configured"}`.
  **코드 fix 는 이미 존재한다** — 폐기 커밋 `9c6661f7` 이 `fix/sweep-2026-09-04` 에만 있고 `origin/main` 은 `c1f61809`.
  백엔드도 동일 갭: `origin/main:routes/auth.py:38-39` 가 `_safe_next("/beta") → "/beta-gate"` 유지
  → OAuth `next=/beta` 로 들어온 사용자가 로그인 성공 후 **죽은 비밀번호 벽에 착지**.
  → **신규 코드 불필요. 머지+배포 = CEO 액션** (`feedback_push_workflow`).

- [ ] 🟠 **P1 — `/docs` 가 존재하지 않는 브로커 연결 기능을 안내 (설정 화면과 정면 모순).**
  라이브 `/docs`: `"Settings → Brokers → Connect KIS (read-only)"`
  vs `settings/page.tsx:653-655`: `"증권사 계좌 연결은 제공하지 않습니다."`
  `/api/broker/{connections,kis/connect,kis/status,kis/sync,kis/disconnect}` **전부 404** (`routes/broker_oauth.py` 삭제됨).
  런타임 404 는 안 남 — `lib/hooks.ts:452` 가 `useSWR(false && …)` 로 요청 차단, UI 는 `BROKER_LINKING_AVAILABLE=false` 게이트.
  **문서 카피만 문제**: `frontend/src/app/docs/page.tsx:21,25,42`.
  ⚠️ 공개 문서가 없는 기능을 "제공한다"고 광고하는 형태 → **표시광고법 §3 각도로 P0 승격 여지, 법무 판단 필요.**

- [ ] 🟡 **P2 (escalate, 확신도 ≤50% — 단독 확정 금지) — `pre-trade-questions.ts:98` 이 SoT 금칙어 '목표가' 포함.**
  `"목표가는 어디까지 보나? 손절까지의 거리 대비 적어도 2배인가?"` — `FORBIDDEN_DIRECTIVE_TERMS` 에 `'목표가'` 정확히 존재.
  단 `scripts/legal/scan_advisory_vocab.py` 는 `clean ✅` → 스캐너 커버리지 갭인지 의도된 예외인지 불명.
  → `legal-kr-fintech` 판단 필요. ⚠️ `feedback_legal_filter_design`: 스캐너를 "고치는" 방향 금지.

- [ ] 🟡 **P2 묶음 (fix 강제 아님, `feedback_no_busywork`)** — #6 `robots.ts:21-31` trailing-slash 로 `/mirror` 미차단
  · #7 sitemap/robots Host=apex vs canonical=www · #8 `<title>` 누락 3곳(`/mirror` 앱 홈 포함, `/support`, `/support/inbox`)
  · #9 `/support` FAQ 가 제거된 "시그널 라벨" 설명 유지 · #10 `lib/endpoints.ts` 죽은 상수 22개(호출자 0)
  · #12 `/landing`·`/beta` 가 307 아닌 200+1초 meta-refresh · #13 처리방침이 폐기된 Stripe 를 수탁자로 계속 고지(과다고지 → P0-1 수정 시 동반 정리)
  · #14 전 라우트 `Cache-Control: no-store`(nonce CSP 부작용, **버그 아님 기록용**)

### 이번 런에서 CLOSE 된 이월 항목
- ✅ **P0급 인프라 블로커 B4 "Render 첫 배포 미완료"** — 해소. `pivoxquant-api.onrender.com/api/health` → **200** `{"db":"ok","missing_required":0}`.
- ✅ **P1 "prod 프론트 배포가 09-01 에 멈춤"(어제)** — 해소. Vercel Production Ready 배포 **5시간 전** 3건(`vercel ls` 실측).
- ✅ **P1 "`www.pivoxquant.com/api/*` 404 (프록시가 죽은 Railway 향함)"** — 해소.
  `/api/health` 200, `/api/billing/availability` 200 `{"available":false,"code":"BUSINESS_REGISTRATION_PENDING"}` = Stripe kill-switch 정상 동작.
- ✅ **P2 "라이브 CSP `connect-src` 가 죽은 `*.railway.app` 지시"** — 해소. 라이브 헤더 실측:
  `connect-src 'self' https://*.onrender.com …`, 응답 헤더에 `railway` 문자열 **0건**.
- ✅ **P2 "비로그인 아바타가 '게' 한 글자"** — 코드 fix 존재(`9cc2172e`), 단 **미머지** → 위 `/beta-gate` 와 같은 배포 갭에 묶임.

### 오탐 / 재보고 금지
- ❌ `/pricing` 307 · `/home` `/market` `/ai-chat` 등 308 — **의도된 라우트 통합**(2026-08-31 prune). finding 아님.
- ❌ `pivoxquant.com` 전 경로 307 — **apex→www 정규화**. 실제 호스트는 `www.pivoxquant.com`. 스윕은 www 로 할 것.
- ❌ Render 첫 요청 40~60s — **free plan spin-down 알려진 특성**. 웜 이후 실측 0.405~0.910s 로 정상.
- ❌ 프로드 JS 의 `"BUY"/"SELL"` 12건 — 전부 내부 enum. `sideLabel()` 이 `ENTRY:"진입"/EXIT:"정리"` 로 정규화. 법적 회귀 아님.

### 2026-09-06 상태 점검 (세션 실측 — 위 09-05 항목을 하나씩 다시 쟀다)

프로드 빌드는 **`main` @ `78755922`** (#548, `www.pivoxquant.com/sw.js` `CACHE_VERSION` 실측) 로 09-05 기록(`c1f61809`)에서 전진했다.
브랜치 `fix/sweep-2026-09-04` 는 `origin/main` 보다 **21커밋 앞·1커밋 뒤** — `78755922` 를 아직 안 품었다. 푸시 전에 main 을 합칠 것.

| 09-05 항목 | 09-06 실측 | 상태 |
|---|---|---|
| 🟥 P0 처리방침 §6 수탁자 3중 오류 | `privacy-ko.md:26-27,167-168` 이 Render(미국)·Supabase(서울 리전) 두 행으로 정정돼 있음 (`ba6dfe48`). **origin/main 에는 없다** → 라이브는 아직 옛 문구 | 🟡 코드 fix 완료 · **미배포** |
| 🟠 P1 FMP 429 | `stable/quote?symbol=SPY` → 여전히 `Limit Reach`. CEO 플랜 판단 대기 | 🔴 open (외부) |
| 🟠 P1 랜딩 US 티커 3칸 `—` | 라이브 `/api/public/market-snapshot`: KOSPI/KOSDAQ/USDKRW **fresh**, `^GSPC/^IXIC/^VIX` `value:null is_stale:true`. FMP 해소 전엔 불변 | 🔴 open (위와 동일 원인) |
| 🟠 P1 `/beta-gate` 500 | 라이브 `/beta-gate` → **404**. 폐기 커밋이 배포됐다 | ✅ closed |
| 🟠 P1 `/docs` 브로커 연결 안내 | 라이브에 `"Settings → Brokers → Connect KIS"` **아직 노출** (origin/main 도 동일). 이 세션에서 `docs/page.tsx` 4문장 수정 — 연결 기능·KIS 자격증명 언급 제거, 설정 화면 문구와 일치 | 🟡 코드 fix 완료 · 미배포 |
| 🟡 P2 `pre-trade-questions.ts:98` '목표가' | 그대로. 유저 본인 질문("목표가는 어디까지 보나")이라 자문 어휘가 아니라는 해석이 가능하나 **단독 확정 금지** 원칙대로 legal 판단 대기 | 🟡 open (legal) |
| 🟡 P2 #6 robots trailing-slash | `robots.ts` 대시보드 7경로를 슬래시 없는 prefix 로 변경 | ✅ fixed (미배포) |
| 🟡 P2 #10 endpoints.ts 죽은 상수 22개 | `ac4ccb0f` 가 정리. 그 여파로 `dormant_endpoints.txt` 의 `/api/artifacts/*` 11줄이 **5일 연속 STALE** 로 보고되고 있었음 → 오늘 prune. `check_endpoint_contract.py`: STALE 0 · OK 74 | ✅ fixed |
| 🟡 P2 #13 처리방침 Stripe 과다고지 | `privacy-ko.md:174,179` 가 "유료 전환 시 적용·현재 이전 없음" 으로 한정 서술. 과다고지 아님 | ✅ 해소 판정 |
| 🟡 P2 #8 `<title>` 누락 · #7 Host 불일치 · #9 support FAQ · #12 meta-refresh · #14 no-store | 미착수 | 🟡 open (busywork 아님 판정 시만) |

야간 리포트 5개(`docs/qa/nightly-verify-2026-09-0{4,5,6}.md`, `virtual_user_sweep_2026-09-0{4,5}.md`)는 `.gitignore` 의 "docs/qa 리포트는 의도적으로 추적" 규칙대로 이 커밋에 같이 넣는다.
09-06 03:03 리포트의 수치(pytest 2000 · vitest 367)는 **온보딩 v3 커밋 `c1427a0f` 이전** 스냅샷이다 — 이후 실측은 pytest 1995 / vitest 368 (V2 테스트 29건 삭제 + v3 22건 신규).

## 2026-09-07 (daily-sweep, prod, Mon) — DETECTION-ONLY

**P0=0 · P1=1 · P2=1 · 자동수정 0건.** 자동수정 단계는 **P0 이 0건이라 발화하지 않았다**(가드 때문이 아님). 워킹트리에 앱 소스 미커밋 없음(dirty 서브모듈 `.claude/skills/ui-ux-pro-max` + untracked QA 리포트만).

자동 레그 전부 green: virtual-user 20명 **516 calls / 0 findings** · pytest **1995 pass / 0 fail** (18 skip, 1 xfail) · tsc 0 · vitest **368 pass** · prod 라우트 14개 전부 200(apex→www 307 경유) · 백엔드 `/api/health` 200 `db:ok` `missing_required:0`.
CAUS = retired(`938bfcf4`). PDF 172-케이스 매트릭스 = 월요일이라 스킵(일요일 전용).

### 🟠 P1 (1건)
- [x] **P1 — `/portfolio` 포지션 행이 "클릭 가능한 링크"로 보이지만 아무 데도 안 간다(죽은 클릭 + a11y 오고지).** `frontend/src/components/portfolio/v2/positions-table-v2.tsx:406-408` 이 삭제된 `/detail/[ticker]` 로 `router.push` 하는데, `frontend/next.config.ts:78` 이 `/detail/:path* → /portfolio` 로 **permanent 리다이렉트** → 클릭하면 **보고 있던 그 페이지로 되돌아온다**(실측 체인: `/detail/AAPL` → 308 → `/portfolio`).
      행에는 `cursor: pointer`(같은 파일 :421) + `role="link"` + `tabIndex={0}`(:473-474) 이 붙어 있어 **스크린리더에 링크로 announce 되고 키보드 포커스도 잡힌다** — 즉 시각/보조기술 양쪽에 "여기 누르면 뭔가 열린다"고 알린 뒤 아무 일도 안 일어난다.
      원인: 2026-08-31 detail 페이지 prune(`47a5e8f3`/`5ed8a23d`) 이 이 소비자를 같이 정리하지 않음. **같은 prune 의 다른 소비자(top-bar 검색)는 이미 정리됨**(`components/layout/top-bar.tsx:11` 주석이 그 이유를 기록) → 단순 누락 1건.
      ⚠️ 자동수정 안 한 이유 = **P1 은 정책상 CEO 리뷰 대상**(auto-fix 금지). 또한 fix 방향이 택일 사항이다: ① row-click/role/tabIndex/cursor 를 통째로 제거(정적 표로) vs ② 행을 journal/pre-trade 등 살아있는 목적지로 재연결. ②는 제품 결정이라 에이전트 단독 확정 부적절.
      잔여 동일 패턴 점검 완료 — 소스의 `/detail/` 참조는 이 1곳뿐이고 나머지는 주석·테스트 픽스처(`lib/demo.ts`, `__tests__/ai-label-coverage.test.ts`)라 런타임 영향 없음.

### 🟡 P2 (1건 — 카운트만, 참고 기록)
- **P2 — `/api/inbox` 미인증 응답이 앱 표준 계약을 위반한다(302 HTML vs 401 JSON).** `routes/inbox.py:14,39` 만 `@login_required`(flask-login)를 쓰고 나머지 API 라우트가 쓰는 `@api_auth` 를 안 쓴다. 실측: `GET /api/inbox` → **302** `text/html` → `/?next=%2Fapi%2Finbox` / 대조군 `GET /api/support/inquiries` → **401** `{"code":"SESSION_EXPIRED",...}`.
      **실사용 영향 낮음**: 프론트 소비자 0건(실제 `/support/inbox` 화면은 `/api/support/inquiries` 를 씀) + ADMIN_EMAILS 전용 CEO 내부 라우트. 유저 노출면·법적 표면 아님.

### ✅ 이월 항목 중 오늘 닫힌 것
- **CLOSED — 09-05 P1 `/docs` 가 삭제된 브로커 연결 기능을 광고(표시광고법 §3 각도).** 라이브 실측으로 해소 확인: `/docs` 가 이제 "Can I connect my brokerage account? **Not in this beta**", "Do I need to connect a broker? **No — and there is nothing to connect**", "No broker credentials are collected" 로 서술한다. `Settings → Brokers → Connect KIS` 문구 소멸.

### ✅ 같은 날 늦게 닫힌 것 (CEO 지시, 18:49~19:0x KST 수동 세션)

- **CLOSED — 위 P1 `/portfolio` 죽은 행 클릭.** `5359d9e8`. 리포트가 남긴 택일에서
  **①(어포던스 제거)** 을 골랐다. 근거는 제품 취향이 아니라 선례다 — 같은 prune 의
  다른 소비자인 top-bar 가 "결과가 `/detail/[ticker]` 로만 갔다"는 이유로 Cmd+K
  팔레트를 이미 지웠고(그 파일 :11 주석), ②(살아있는 목적지로 재연결)는 리포트가
  적은 대로 제품 결정이라 수동 세션에서도 단독 확정 대상이 아니다.
  `role="link"` · `tabIndex` · `onKeyDown` · `cursor:pointer` · `router.push` 제거,
  hover 틴트와 Add/Trim/Edit 버튼은 유지. `:hover` 에만 걸려 있던 액션 노출에
  `:focus-within` 추가 — 행 자체가 포커스 가능할 땐 넘어갈 수 있었지만 이제는 아니다.
  파일 헤더 독스트링이 아직 옛 클릭을 기술하고 있어 같이 고쳤다.
  **회귀 테스트 4종 신규**(`positions-row-not-a-link.test.tsx`) — 이 컴포넌트를
  렌더하는 테스트가 **0개**였던 것이 이 링크가 prune 을 살아남아 야간 스윕에서야
  발견된 이유다. 이전 리비전에 대고 돌려 4개 전부 실패함을 확인해 공허하지 않음을
  검증했다.

- **P2 `/api/inbox` 는 열어 둔다.** 프론트 소비자 0 + ADMIN 전용이라 이번에 손대지
  않았다. 카운트 유지.

- **재스윕(18:49) 결과 — P0 0 / P1 0 / P2 1.** pytest **2021 pass / 0 fail**(18 skip,
  1 xfail) · vitest **372**(368+신규 4) · tsc 0 · eslint 0 · next build exit 0 ·
  부팅 `rules 121 / bp 23`(friction-outcome 라우트로 120→121) · 엔드포인트 계약 OK
  74/74 · 법적 방어선 **229 pass** · 가상 유저 20명 **516 calls / 0 findings** ·
  prod 프론트 `/ /docs /login /privacy /terms` 200(`/pricing` 307 의도됨) ·
  백엔드 `/api/health` **`db:ok` `missing_required:0`**.
  ⚠️ 세션 시작 hook 의 `backend=404` 는 **틀렸다** — Render 콜드스타트였다.

  **이 재스윕이 덮지 못한 것 두 가지**(로컬 환경 한계, prod 문제 아님):
  `FMP_API_KEY` 미설정이라 가상 유저의 시세 콜이 전부 에러 → **시세 표면은 검사되지
  않았다**(516/0 이 아침과 같은 이유). `SENDGRID_API_KEY` 미설정이라
  `email_compliance_check` **SKIP** → 이메일 발송 컴플라이언스 **미측정**.

- **`section101_compliance_check` 가 exit 1(광고성 키워드 21건)을 내지만 조치 없음.**
  스크립트 스스로 "위반 '가능성' 힌트"라고 적는 키워드 존재 스캔이고 표본이 오탐이다:
  `opengraph-image.tsx` 는 주석의 **표시광고법**(부분문자열), `no-free-trial-copy.test.ts`
  는 그 문구를 **금지하는** 테스트, 동의 문구의 `광고성 정보 수신 동의` 는 정통망법
  §50④ 가 **요구하는** 표기다. 오늘 수동 세션 커밋이 추가한 `광고` 는 0줄
  (`git diff 180b4bc2..HEAD -- frontend/src | grep -c '^+.*광고'` = 0). 상시 조건.


## 2026-09-08 (daily-sweep, prod, Tue) — DETECTION-ONLY

**P0=1 · P1=1(이월 재확인) · P2=3 · 자동수정 0건.** 가드 발동: 미커밋 사용자 작업(`frontend/public/sw.js` CACHE_VERSION + dirty 서브모듈) → fix/commit 단계 전면 스킵. 상세: `BUG_SWEEP_2026-09-08.md`.
자동 레그 전부 green: virtual-user 516 calls/0 findings · 야간 pytest 2063/0 · tsc 0 · vitest 382/382 · eslint 0 · next build 0 · 죽은 import 0 · 엔드포인트 계약 74/74.

### 🟥 P0 — 표시광고법 (자동수정 보류 = 가드, 코드상 fix 는 카피 2줄로 단순)
- [ ] **P0 — 랜딩 FAQ 가 법적 사유로 삭제된 KIS 증권계좌 연동을 광고 중(라이브).** `frontend/src/messages/ko.json:92-93` (a5) + `en.json:81-82`. 프로드 실측 렌더: *"제 증권계좌에 접근하나요? / Read-only. KIS (KR) read-only scope로 연결됩니다. 주문 · 출금 · 수정 불가… 연결 해제 시 시세 동기화가 멈추고"*.
      **기능은 존재하지 않는다(4중 실측)**: `settings/page.tsx:93` `BROKER_LINKING_AVAILABLE = false` / `(auth)/onboarding/broker/page.tsx:29-44` "KIS connect·sync·disconnect·status 5개 라우트는 법적 사유로 삭제"(KIS 제휴가 비인가 사업자에 닫힘, 토스 오픈API §5②) / prod `GET /api/broker/kis/status` **404**, `/api/broker/connections` **404** / `lib/hooks.ts:453` 키 `false && API.broker.connections` 로 하드 비활성.
      **같은 사이트가 정반대를 말한다** — 공개 `/docs`: *"Account linking is not offered" · "there is nothing to connect" · "No broker credentials are collected."* 기능 철회 시 코드 경로는 전부 닫혔고 **마케팅 카피만 누락**됐다. 표시광고법 §3(거짓·과장 표시).
      CEO 액션: 카피 정정 방향(연동 문항 자체 삭제 vs `/docs` 문구와 동일하게 "연동 없음"으로 재작성) = 제품·법무 판단이라 에이전트 단독 재작성 보류. **가드 해제되면 즉시 fix 가능한 최소 변경**(ko/en 각 1문항).

### 🟠 P1 (이월 1건 — 재확인 + 신규 증거)
- [ ] **P1 — `/support` 가 폐기된 유료 3-tier 와 제거된 AI 챗봇을 계속 안내**(09-02 부터 열림). `messages/ko.json:295-296, 319-320` + `en.json:296, 320`, **추가 발견: `frontend/src/app/support/page.tsx:146` 하드코딩**. `support/page.tsx:125-133` 의 `isAuthed` 분기는 1:1 문의 + 내 문의함만 제공 → 약속된 AI 채널은 **로그인 후에도 끝내 나타나지 않음**이 코드로 증명됨. 본문이 가리키는 "요금 안내 페이지" 는 `/pricing → 307 /mirror`. P0-1 과 **동일 패턴(철회된 기능의 카피 잔존)** → 전수 마감 권고.

### 🟡 P2 (3건 — 카운트 + 기록만, 자동수정 대상 아님)
- [ ] P2 — `/support` 가 루트 canonical 을 상속해 **홈페이지를 자기 canonical 로 선언**(`layout.tsx:164-166`, 다른 공개 페이지와 달리 override 없음)
- [ ] P2 — `sitemap.ts:3`·`robots.ts:3` 이 apex 호스트 하드코딩 → sitemap 7개 URL 전부 307 리다이렉트, 실제 서빙 canonical 은 www
- [ ] P2 — `robots.ts` 가 인증 대시보드 라우트를 전부 disallow 하면서 `/support` 서브트리만 예외 → `(dashboard)/support/inbox/[id]` 가 노출 대상에 포함

### ✅ 이번 회차 CLOSED
- [x] ~~**P1 — `/portfolio` 포지션 행 죽은 클릭**(삭제된 `/detail/[ticker]` → 308 자기 자신, 스크린리더에 링크 오고지)~~ **CLOSED — `5359d9e8`.** `positions-table-v2.tsx:446+` 가 평범한 `<tr>` 렌더로 전환 + 회귀 테스트 동반.

### 🟠 P1 신규 (2026-09-08 legal-guard)
- [ ] **P1 — Alpaca 마켓데이터 어댑터의 라이선스 정당화가 stale.** `services/data/alpaca_market_adapter.py` 모듈 독스트링이 상업적 재배포 권리를 *"we already subscribe as part of the brokerage relationship"* 로 근거 삼는데, 그 브로커리지 관계는 `562d2b85`(Alpaca 제거)에서 사라졌다. **현재 노출 0** — `alpaca_market_adapter.py:74` `ALPACA_ENABLED` 기본 `"0"` = OFF. 다만 `services/data/fmp.py:389`, `services/data/fetcher.py:647·1341` 에 FMP 폴백으로 배선돼 있어 **env 한 줄로 켜진다**. `research_fmp_replacement.md`(2026-06-07)의 "Alpaca market-data 재도입 = 변호사 필수" 와 정합. 액션: ① 독스트링의 죽은 라이선스 전제 정정(사실관계 오기) ② 켜기 전 약관 재확인 = 변호사 큐. 코드 fix 아님 — **가드 발동으로 이번 회차 미수정**.

## 2026-09-09 (daily-sweep, prod, Wed) — DETECTION-ONLY (2일 연속 가드)

**신규 P0=0 · P1=4 · P2=0.** 자동수정 0건 — 가드 발동(`frontend/public/sw.js` + dirty 서브모듈). 상세: `BUG_SWEEP_2026-09-09.md`.
자동 레그: virtual-user **516 calls / findings 0** · 라우트 14종 200 · NaN/undefined 0건 · 매수/매도 지시어 0건. ⚠️ **야간 빌드 게이트는 미완주 = 오늘 빌드 보증 없음**(P1-1).

### 🟠 P1 신규 (4건 — 자동수정 금지, CEO 검토)
- [ ] **P1 — 야간 빌드 게이트가 2시간+ 정지한 채 조용히 열려 있다(fails open).** `nightly-verify-2026-09-09.md` = **11줄**(09-08 은 103줄·6섹션), ` ``` ` 펜스 연 채 절단, 섹션 3~6 부재. 프로세스 생존 확인: `36766 python -m pytest -q` **ELAPSED 02:02:55**, 최초 2시간 CPU 누적 `3:41`(가동률 ~3% = 대기). ✅확정 근본원인: **타임아웃 가드 부재** — `pytest.ini:10` addopts 에 timeout 없음 + `pytest-timeout` 미설치 + `scripts/nightly/verify_build.sh:79` 가 `pytest -q` 무제한 호출. ❓미확정: 어떤 테스트가 멈췄는지(스택은 libcrypto SHA256/PBKDF2 지배하나 3% 가동률과 모순, TCP 소켓 0개, soft-delete SQLite 픽스처 열림). 액션 ①per-test 타임아웃 ②**리포트 절단을 실패로 판정하는 체크**(현재 잘린 리포트가 green 처럼 보임).
- [ ] **P1 — 라이브 이용약관이 삭제된 "시그널" 제품면을 20회 기술.** `/signals` 308(삭제)인데 `/terms` 렌더 텍스트에 `시그널` **20회**, `/privacy` **2회**. 원문: *"POSITIVE / NEGATIVE / NEUTRAL 시그널은 … 분석 결과 관찰값이며"* = 존재하지 않는 산출물을 규율하는 번호 조항. 면책 문맥이라 표시광고법 직격은 아니나 **약관 v2 변호사 큐와 직결**. 🟥 **철회 카피 잔존 4번째**(`/docs`→`/support`→랜딩 FAQ→`/terms`·`/privacy`) — `feedback_thorough_fixes` 적용, 개별 fix 말고 **전수 스캔 1회**(09-08 권고 미이행).
- [ ] **P1 — 그날 첫 요청이 180초 안에 응답하지 않음.** `/api/health` 최초 `-m 180` → `code=000` 무응답, warm 재호출 `200 / 0.59s` (`db:ok`, `v37+`). 메모리 `project_render_migration` 기록값 "스핀다운 50s+" 를 최소 3.6배 초과. `80f53a05`(콜드스타트 43.9s > 타임아웃 30s)와 동일 계열 = **경로 미봉합**. ⚠️ 동일 호출의 `time_total=845s` 는 `-m 180` 과 모순 → 신뢰 불가, 확정 사실은 "180초 내 무응답" 하나. **1회 관측 = 재현 전 단정 금지**(재현엔 15분 유휴 필요).
- [ ] **P1 — 빌드 산출물이 트리를 상시 더럽혀 자동수정을 2일째 봉쇄.** 가드를 발동시킨 `frontend/public/sw.js` 는 사람 코드가 아니라 **빌드 스탬프**(diff 1줄: `pq-build-ef755198`→`032fb7b2`, 파일 주석 자체가 *"the build script does this work"*). 스탬프가 **HEAD `921dff4d` 보다 2커밋 뒤** = 복구되지 않은 잔재. `verify_build.sh:96-107` 의 snapshot→복원 계약은 **그 스크립트 밖 빌드엔 적용되지 않음**. 결과: 안전장치가 **상시 차단기로 퇴화**해 라이브 P0(랜딩 FAQ 허위광고)의 수정을 이틀 붙잡는 중. CEO 판단 3택: ①스탬프 라인을 가드 판정에서 제외 ②커밋 대상에서 빼고 배포 시 주입 ③현재 스탬프를 HEAD 로 맞춰 커밋.

### 🔁 이월 재확인 (오늘 실측 — 전부 그대로 라이브)
- [ ] 🟥 **P0 (09-08 이월) 랜딩 FAQ 가 삭제된 KIS 연동을 광고 중** — `messages/ko.json:92-93`·`en.json:81-82` 문구 **오늘 재확인, 변동 없음**. 표시광고법 §3. **가드 때문에 이틀째 미수정.**
- [ ] P1 (09-02~) `/support` 폐기 3-tier·제거된 AI 챗봇 안내 — `support/page.tsx:146` 하드코딩 **그대로**.
- [ ] P1 (09-08) Alpaca 어댑터 독스트링 라이선스 전제 stale (노출 0, `ALPACA_ENABLED=0`).
- [ ] P2 ×3 (09-08) `/support` canonical 상속 · `sitemap.ts`/`robots.ts` apex 하드코딩 · `robots.ts` 의 `/support` 서브트리 예외.

### ❌ 이번 회차 미검증 (PASS 아님)
콘솔 에러 · 네트워크 4xx/5xx · 375px 모바일 · DisclaimerBanner · naked ticker 회귀 — 인증 라우트가 클라이언트 셸(50.6~51.9KB 동일 크기대)이라 curl 판정 불가 + 위임한 bug-hunter 가 **브라우저 MCP 도구 없이 기동돼 600초 무진전 실패**.

## 2026-09-10 (daily-sweep, prod, Thu) — 이월 P0 2건 CLOSED

**신규/확인 P0=0 · P1=8 · P2=3.** 자동수정 0건 — 가드는 해제됐으나(어젯밤 `bf759f6c` 가 sw.js 스탬프 정합) **P0 0건이라 트리거 없음**. 상세: `BUG_SWEEP_2026-09-10.md`.
자동 레그: virtual-user **516 calls / findings 0** · 야간 게이트 **완주**(pytest 2063/0fail · tsc 0 · vitest 382 · eslint 0 · build 0 · 계약 74/74) · 라이브 라우트 14종 200 / 삭제 6종 308 · BUY/SELL/HOLD 0건 · NaN·undefined 0건.

### ✅ 이월 P0 2건 종결 (오늘 실측)
- [x] ~~랜딩 FAQ 가 삭제된 KIS 연동 광고 (표시광고법 §3)~~ → `e542bb70`(#553) main 머지 + **라이브 번들에서 배포 확인**(수정 카피 존재 / "40 quant models"·"7-layer"·"CFO" 0건)
- [x] ~~PIPA §28-8 국외이전 고지의 Railway 잔존·Render/Supabase 누락~~ → `privacy-ko.md:167-168` Render·Supabase 각 행 + `:183-188` Railway 해지 명시

### 🟠 P1 신규 (8건 — 자동수정 금지, CEO 검토)
- [ ] **P1 — US 지수 3종 null 의 근본원인 확정(2일 미확정 해소). 액션 = Render env 에 `FMP_API_KEY` 설정.** 사슬: `market.py:753` US=ETF 프록시만 → `fetcher.py:317` US 체인 = Alpaca→FMP→FMP profile → `config.py:65` `ALPACA_ENABLED` 기본 **"0"** = 프로덕션 OFF → 유일 소스 FMP → prod health `missing_recommended:1` 중 recommended 는 정확히 3개(`FMP_API_KEY`/`KIS_APP_KEY`/`KIS_APP_SECRET`, `launch_prep.py:140-149`)이고 **KR 지수 fresh 가 KIS 두 키의 존재 증명** → 빠진 건 FMP → `_etf_snapshot` ×5 None → snapshot `[]` → `market.py:895` 가 **빈 결과를 캐시 안 함** → 에러 신호 0 으로 무기한 null. ⚠️ 마지막 링크만 추론(health 는 개수만 반환) — Render env 화면에서 즉시 확정 가능. 09-04 이관 env 유실 패턴(`SIM_ONBOARD_SECRET` 건)과 동일 계열 의심.
- [ ] **P1 — 백엔드가 ~50초간 전면 502, 헤더 `x-render-routing: no-deploy`.** 03:45:40 health 200 → 03:45:50~03:46:11 전 엔드포인트 502(www 프록시·Render 직접 **양쪽**, 응답 0.15~0.5s = **콜드스타트 아님**; 콜드스타트는 별도로 43.6s 관측) → 03:46:29 자가복구, 이후 5/5 200. 그 창의 유저는 재시도 없이 API 전면 실패. ⚠️ **1회 관측 — 원인 단정 금지**(유력: free plan 스핀다운 전환). 09-09 P1 "첫 요청 180초 무응답"과 같은 뿌리로 보이며 오늘 시그니처가 훨씬 선명.
- [ ] **P1 — `/settings` 가 삭제된 아티팩트 리포트 이메일을 약속.** `settings/page.tsx:885` 토글 옆 "모든 리포트가 PDF + HTML로 이메일로 발송됩니다". 실측 `services/artifacts/` **부재**, 남은 템플릿 6종(onboarding 3·retention 2·customer 1)에 **리포트 템플릿 0건**. 토글 자체는 실존 메일을 제어하므로 거짓보다 **과대 기술**.
- [ ] **P1 — `/support` FAQ 가 삭제된 "시그널 라벨" 사용법을 안내.** `faq-section.tsx:84`,`:116` **2곳 렌더**, POSITIVE/NEGATIVE/NEUTRAL 설명. `/signals` 308.
- [ ] **P1 (09-09 이월) — `/terms` 가 삭제된 "시그널" 제품면을 10회 기술.** `terms-ko.md:110` 제6조 제목이 "시그널·인공지능 미사용·백테스팅 면책", `:50` 이 POSITIVE/NEGATIVE/NEUTRAL 을 번호 조항으로 정의. 라이브 렌더 시그널 10·Signal 2. **법적 위반은 아님**(BUY/SELL/HOLD 0, 매수·매도 3/3 전부 "권유가 아닙니다" 부정문) — 약관 v2 변호사 큐와 직결.
- [ ] **P1 — topbar 알림 드롭다운이 삭제된 시그널 참조.** `notification-dropdown.tsx:231` "시그널이 관측되면 여기에 표시됩니다". `/alerts`·`/signals` 308.
- [ ] **P1 — 주문 메서드 회귀 감지기가 fails open.** `~/.claude/memory_tools/memory_audit.sh:45` 는 `def place_order|execute_trade|submit_order` 를 찾는데 실제 이름은 `buy_order`(`services/kis/service.py:506`)·`sell_order`(`:520`)·`_place_order`(`:534`) — 전부 미매칭(`def place_order` ≠ `def _place_order`). 오늘 셋 다 무력화 확인(`KIS_READ_ONLY` 반환·HTTP 호출 없음) = **현재 위험 0**. 결함은 실제 이름으로 주문이 되살아나도 훅이 계속 "0건 정상"을 보고한다는 것. `94cd7818` 로 고친 야간 게이트와 동일한 fails-open 계열. 3일째 지적.
- [ ] **P1 — 위임 bug-hunter agent 구조적 불능(2일 연속).** agent 정의 도구명이 `mcp__Claude_in_Chrome__*`, 실제 서버는 `mcp__claude-in-chrome__*`(케이스 불일치) → 브라우저 도구 없이 기동, 8분 산출 0 으로 중단. 09-09 에도 동일(600초 무진전). 자동화 탐지 레그가 이틀째 lead 수작업으로만 성립.

### 📌 철회 카피 — 전수 스캔 이행, 목록 종결
09-08 부터 3일 연속 권고된 **"개별 fix 말고 전수 스캔 1회"** 를 이번 회차에 이행(i18n json + content md + 이메일 템플릿 × 20개 용어). **남은 표면은 위 4건뿐**(settings·support FAQ·terms·topbar)이며 목록은 닫혔다. 넷을 한 번에 처리하면 종결.

### 🔵 P2 ×3
`consents.ts:180-183` 주석의 Railway 잔존(비노출, 고지 SoT 는 정확) · `dormant_endpoints.txt` 3건 prune · `/support` canonical + sitemap/robots apex 하드코딩(09-08 이월).

### ❌ 미검증 (PASS 아님, 3일 연속 사각지대)
인증 페이지 **콘솔 에러·네트워크 4xx/5xx·375px·DisclaimerBanner·naked ticker**. 인증 라우트가 클라이언트 셸("Loading…"만 SSR)이라 curl 판정 불가 + 세션 브라우저가 `pivoxquant.com` **정책 차단** + 위임 agent 불능. 해소 경로 = carry-over B7(브라우저 로그인 1회 직접 확인).
