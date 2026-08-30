# PivoxQuant — 인수인계서 (2026-06-12 v66 — 버그헌트 14건 처분 + 가상유저 3-레이어 감사·구축 완료)

## v66 2026-06-11~12 — CEO "버그들 다 진행 + 가상유저 구축 제대로 됐는지 파악하고 구축해놔라" (야간 자율)

> **Part A — 버그헌트 14건 처분 완료**: 11건 fix + 3건 근거 있는 no-fix (#4 interactive-before-tier = 테스트로 고정된 의도 + 프론트 도달 불가 / #8 observed_at = 관측시각이 정답 / #11 TOCTOU = max_instances=1로 실위험 없음, reserve/refund 배관이 더 위험). 커밋 4개: `9b9810b7`(백엔드 6건) `e4dd5f4e`(AI예산 — **인터랙티브 AI 라우트 일일 캡 신설** swot/competitor/sector-trend/commentary/morning-summary/coaching, 2000/day 글로벌 breaker, env `PIVOX_INTERACTIVE_AI_DAILY_LIMIT`, 2xx만 소비/장애시 fail-open) `30150213`(discover **proxy_ticker 고지 배지** "via SPY" + reports pickLatest sent_at??created_at + living_mirror 통합 다운로드 415 fix) `ff9ea9a1`(ruff F401/F541 12건 정리).
>
> **Part B — 가상유저 3-레이어 감사 결과 + 구축** (CEO 질문 "구축 제대로 된건지"에 대한 답: **레이어별로 반쪽이었고, 이제 전부 실동작**):
> - **L1 아티팩트 렌더 매트릭스 (10명×17종=172케이스)**: HTML 브랜치만 살아있고 **PDF 브랜치는 생성 이래 전부 xfail** (macOS dlopen libgobject 실패). conftest+run.py에 darwin 전용 `DYLD_FALLBACK_LIBRARY_PATH` 부트스트랩(`8dd91d2c`) → **172/172 passed 첫 완주** (24m, PDF 렌더+크기+pypdf 추출+§101 마커 실검증). 로컬 dev 서버 PDF 다운로드도 함께 해결. 풀 PDF는 스위트 +24m이라 **`PIVOX_MATRIX_PDF=1` 옵트인 게이트**(`a569b2ec`) — 기본 스위트는 HTML 상시 검증, 일요일 cron이 풀 매트릭스 (SKILL.md 반영).
> - **L2 API 스위프 (20 가상유저)**: 10 엔드포인트 read-only였던 걸 **40 엔드포인트 + tier별 generate leg + 음성 권한체크(inbox 403 고정) + proxy 고지 패리티 + structured-degradation 검증**으로 확장(`5f928734`). cron이 git-guard에 자주 스킵되는 구멍 → **pytest 게이트 신설**(`tests/test_virtual_user_sweep.py`, N=6, 스위트 상시 편입). 최종 실측: **991 calls, 0 findings**.
> - **L3 CAUS (브라우저 1명/일)**: **수 주간 가짜-클린이었음을 적발** — sim 세션 만료(수명 1일, 파일은 5/13-17산) + `/tmp/sim-onboard-secret.txt` 재부팅 소실 상태에서 **세션 없음 스텁이 "findings: 0 clean run"과 동일 포맷**으로 기록돼 옴. fix(`7f04ee1a`): ① 스텁 → `status: SKIPPED` 정직 기록 ② **public 시나리오(day6/8)는 세션 없이 실행** ③ `_pass_beta_gate()` — `PIVOX_BETA_PASSWORD`로 베타게이트 쿠키 자동 발급 ④ un-stub 첫 실행이 곧바로 P0 5건 발사 → **전부 가양성**(법적 필수 면책문구 "매수·매도를 권유하지 않습니다"가 금지어 스캔에 걸림, #509-513 close) → `grep_forbidden` **부정문 인지(문장 단위)** 로 수정+회귀테스트 4종. 재실행 = prod 실 브라우저 런 **0 findings (진짜 clean)**, `auto-sim-reports/2026-06-12.md` status: ran.
>
> **부수 발견**: ⓐ **로컬 dev 서버 wedge 재발 규명** — 8h 후 스레드 2,049개/SQLite FD 290/CPU 80%, `*/2분` ops cron 동일 슬롯 4-5중 동시실행 (Mac 수면 후 misfire 폭풍 의심). prod 무관(불면). **이슈 #514** (fix는 app.py cron 인프라라 CEO 결정 대기 — 후보: dev는 RUN_SCHEDULER=0 / executor 상한 / misfire 설정 검증). ⓑ `com.pivoxreport.*` LaunchAgents는 **다른 프로젝트**(~/dev/pivoxreport)인데 bug-hunter-daily SKILL.md가 pivoxquant 서버로 오참조 — SKILL.md 정정, 세션 중 잘못 kickstart했다가 bootout으로 원복(plist 보존, 재로그인 시 자동 로드 복귀).
>
> **검증**: vitest **573/573** + tsc clean + artifact 매트릭스 **172/172** (PIVOX_MATRIX_PDF=1) + sweep **991 calls/0 findings** + CAUS prod 실런 0건 + 백엔드 full suite **3951 passed/1 fail** — 그 1 fail 은 weasyprint-unavailable 가정 테스트가 부트스트랩으로 깨진 것 (내 변경의 직접 후폭풍) → render_pdf mock 으로 결정론화 후 모듈 18/18 재검증 (v66 마지막 커밋). 기본 스위트 소요 ~22m (sweep 게이트 +1.5m 포함).
>
> **CEO 액션 (가상유저 인증 시나리오 복원에 필요)**: ① `SIM_ONBOARD_SECRET`을 cron env에 복원 (Railway Variables에서 확인. /tmp 파일은 소실) ② 이슈 #514 fix 방향 결정. 이 둘 빼고 가상유저 3-레이어는 전부 자동 운영 가능 상태.

---

## v65 2026-06-11 — CEO "다 진행해봐" → "하던거해라계속" (B2 tier 정렬 완결)

> **B2 = 가격표↔코드 tier 9건 불일치 (v64 감사 확정, CEO 가격결정 대기였던 건) — 코드를 가격표에 정렬 완료** (`afff4fb6`).
> 방향: 감사 권고(가격표→코드)와 반대인 **코드→가격표** — 광고된 약속 이행이 표시광고법상 가장 방어적, 결제 OFF라 오늘 수익영향 0. tier 재단 시 EXPECTED_TIER+pricing/page.tsx 동시 수정.
> - **4개 백엔드 표면 정렬**: ① 서비스별 `_PAID_TIERS` cron fan-out 9개 ② `@require_tier` preview/download 라우트 ③ risk-board VIX force-fire → PRO_AND_UP ④ **unified `/generate` `_ARTIFACT_MIN_TIER`** (이전 세션이 ①~③까지 하고 ④를 누락한 상태로 미커밋 — 이번에 발견·완결. 이 맵은 개별 라우트를 우회하는 dispatch 게이트라 누락 시 9건 그대로 잔존이었음).
> - 결과 분포: **Pro 9** (insider_mirror·risk_board·dividend_income·quarterly_self·self_audit·portfolio_segment + 기존 weekly_memo·earnings_prebrief·dd_checklist) / **Premium 6** (kpi_dashboard·credit_rating·burn_rate + 기존 monthly_finance·capital_allocation·year_end_letter).
> - **프론트 정렬**: 랜딩 reports-gallery 배지 9개 재그룹(Pro 10/Premium 6 카드 — **로컬 브라우저 DOM 17카드 전수 실측 일치**) + kpi-dashboard preview TierGate free→premium(Wave-2 drift). reports v1 카탈로그·v2 갤러리/CTA·landing-v2 가격카드·terms는 **이미 일치** (drift는 백엔드+랜딩갤러리+kpi preview뿐이었음).
> - **게이트 테스트 신설** `tests/test_artifact_tier_alignment.py`: EXPECTED_TIER(=가격표) vs 4표면 자동 잠금. tier/artifact 스위트 68 passed·vitest 559/559·tsc clean·**백엔드 전체 3917 passed/0 fail (18m, exit0)** 후 push.
> - **CEO 결정 플래그 2건**: ⓐ 가격표가 **무료 기능을 유료 perk로 광고** — Brag Card(Premium 카드)·S&P 500 Backtest(Pro 카드)는 백엔드 의도적 무게이트(viral/universal). 카피에서 빼거나 유지 결정 필요(테스트 docstring에도 명시). ⓑ /reports v2 **"Risk Note" 타일 죽은 기능** — `type:"risk_report"`가 dispatch에 없어 클릭 즉시 400 (+ 완료 watcher도 risk_board 타입과 불일치). 제거 vs 실제 배선 결정 필요 — 별도 세션 칩 생성됨.
> - **B3 완결** (`ef28bb87`): AI 예산 전역 고정캡(=유료 유저 상한 200명) → `services/ai_budget.py` `DailyAiBudget` 공유 SoT — **effective = max(base, 당일 entitled×1.25)** (run_weekly/run_scan이 cohort note, 누적). env 레버 3개(`PIVOX_WEEKLY_MEMO_AI_LIMIT`/`PIVOX_PREBRIEF_AI_LIMIT`/`PIVOX_EARNINGS_TONE_DAILY_LIMIT`) + 80% 소진 WARNING 1회/일. earnings_tone은 **의도적 전역 유지**(ticker별 90일 공유캐시 — 감사의 "51번째 유저 429"는 51번째 미캐시 ticker에만 해당). zero-arg wrapper 보존(기존 monkeypatch 테스트 무손상). 신규 12 + 영향권 100 + artifact 전역 140 passed.
> - **CAUS 이중화** (v64 아침결정 ②): 실태 = launchd RETIRED 후 **자동 발화 주체 0** (06-09/10 리포트는 야간세션 수동). → `bug-hunter-daily`(03:39, 매일 발화 중) SKILL.md에 **step 0 = 20-유저 sweep + CAUS 브라우저 패스** 편입 + stale 정정(repo 경로 ~/dev→Desktop/취준, 삭제된 /autotrade·격리된 /ai-chat 페이지 제거, autotrader.py 보호목록→frozen_files.yaml 참조). morning-briefing에 **갭 일수 감지** 추가. **Railway 서버 leg는 불가 확정** — sweep이 tests/conftest(pytest) 의존인데 prod requirements에 pytest 없음(defer: conftest 비의존 하네스 별도 빌드). 편입 실증: 오늘 트리(B2+B3 반영)로 sweep **336 호출 0 findings** (`docs/qa/virtual_user_sweep_2026-06-11.md`).
> - **④ 그림자색 토큰화 sweep** (`c3d42737`): Wave-1C 트리플릿 토큰(--pq-bronze-rgb 등)이 **정의만 되고 채택 0**이던 것을 그림자 선언 28곳에 채택 — rgba(트리플릿,α)→rgba(var(--pq-*-rgb),α) (렌더 동일, **브라우저 computed style로 실증**). 제3의 브론즈 #8B6F47 발견 → `--pq-bronze-wash-rgb`로 명명만(캐노니컬 통일 = 시각 변경이라 CEO 디자인 리뷰 항목). **drift 가드 테스트 신설**(`design-token-drift.test.ts` — Tailwind arbitrary 1건을 sweep이 놓친 걸 가드가 즉시 잡아 증명). 배경/그라디언트의 ~1,400 literal은 의도적 범위 밖. vitest 572/572 + **HEAD 격리 worktree 전체 스위트 3929 passed/0 fail** (동시 세션 미커밋 변경 배제하고 push 대상 커밋만 검증).
> - **동시 세션 주의**: Risk Note 칩(별도 세션)이 같은 트리에서 작업 중 — `routes/artifacts.py`(risk_report→risk_board alias)·CTA·hooks 등 미커밋 변경은 **그 세션 소유라 본 세션 커밋에서 제외**함. 파일 겹침 0 확인.
> - **"안한것도 다해라" 추가 마감 4건** (HEAD 격리 worktree 전체 스위트 **3942 passed/0 fail** + vitest 전체 green 후 push): ① **KR 52w 알림 갭 클로즈** (`3ba9564d`) — FIX 2(2026-05-22)가 "KIS 소스 deferred"로 KR 전면 skip하던 것을 `kis_market_adapter.get_52w_range()`(inquire-price `w52_hgpr/w52_lwpr`, 공식피드·₩0)로 빌드, `_lookup_52w_range` KR→KIS 라우팅. KIS 불가 시 missing pair=옛 skip과 동일 안전(오발화 0 계약 테스트로 고정, KR은 FMP 절대 미접촉). 옛 "KR 무조건 skip" 계약 테스트 2파일 재작성+신규 11. ② **가격표 정직화** (`278d6a25`) — 무료인 Brag Card(Premium 카드)·S&P 500 Backtest(Pro 카드)를 유료 perk 목록에서 제거, 카운트 재계산(12→11/seven→six). ⚠️ /pricing은 next.config.ts:66이 /home으로 hard-redirect 중(Stage 0 숨김)이라 현재 노출 0 — Stage 1 대비. ③ **bronze-wash 가족 전체 토큰화** (`e94a8d0c`) — 잔여 96+9 literal까지 105/105 완료, #8B6F47→canonical 통일 결정이 globals.css **1줄**이 됨. 가드 확장(wash literal 전역 0). ④ **deferred 재평가 확정**: DCA XIRR·lookahead·Composer synthetic=owner 명시(수익률 표기 방법론, careful-zone quant)·부분환불 §17=billing+변호사·국외이전 §28-8=변호사 → 보류가 맞음. AUTOPILOT_BACKLOG=부재(축적 P1 없음).
> - carry-over 커밋: 법무 상담 패킷(상담A/B·실행계획·R7 KIS 데이터 옵션)+CEO env 체크리스트+CAUS 리포트 (`30eaaaaf`) / SHIP_BLOCKERS 06-09 정정+FMP free-tier 주석+`.kis_token_cache*.json` ignore 글롭 (`0e0d30fc`).


## v64 2026-06-10 야간 — CEO "버그헌팅+사업·디자인 감사+구조+가상유저 20명+옛 명령 확인, 새벽 동안 다"

> 상세 정직보고: `docs/ops/overnight_report_2026-06-10.md`. 요지:
> - **CAUS("옛 명령") 실태**: 돌아는 감(매일 03:00, 리포트 16개) — 단 **1유저/일** 로테이션 + 6-03~08
>   6일 갭(launchd RETIRED → Claude 스케줄러 의존, 맥 꺼지면 미발화). 보완으로 ↓
> - **20-유저 sweep 하네스 신설** `scripts/qa/virtual_user_sweep.py` (`2d28fd14`): 8 페르소나×3 tier×8
>   포트폴리오 유형, deposition→journal 포함 전 표면, 5xx/NaN/NAV-버킷/journal 무결성 검사. **336 호출
>   0 findings ×2회**. in-process·₩0·수 초.
> - **wave-3 버그헌트 12건 → 10건 수정** (`08c51390`,`c05e4915`): **[P1] NAV alias 버킷팅**(어제 fix가
>   get_portfolio만 커버 — v2가 실제 쓰는 /positions에 같은 버그 잔존, 커밋 메시지의 "형제는 이미 suffix"
>   주장 오류 인정) / **[P1] signal_detail 15s 타임아웃 무효**(with-Executor exit이 wait — 실행 검증,
>   shutdown(wait=False) detach) / twin 주간 수익률(SELL proceeds 분모+₩$ raw-sum → realized/realized
>   KRW-정규화; 에이전트의 BUY-only 제안은 주간 시맨틱 회귀라 수정 적용; 과거 rows는 문서화된 drift) /
>   risk_summary literal NaN(invalid JSON) / **SW 캐시 cross-user**(PIPA export 60분 디스크 캐시 →
>   network-only + user-id 변경 시 SW 캐시 클리어) / `safe_cache_blob()` SoT(corrupt 1행이 응답 전체
>   500내던 13곳 통합) / $0 SL 오발 / refresh null TypeError / detail watchlist normalize / watchlist N+1.
>   보류: SSE slot leak(재설계 필요), rolling_metrics 성능.
> - **사업모델 감사** (`docs/strategy/business_model_audit_2026-06-10.md`): **B2 = 가격표↔코드 9건 불일치
>   실측 확정** — Pro로 파는 6개가 Premium 게이트, Premium 광고 3개가 Pro 배송. 결제 ON 순간 첫 Pro
>   유저부터 깨짐 + 표시광고법. **tier 통일 방향 = CEO 가격 결정 대기** (밤에 안 건드림). B1=§101 vs
>   월구독(변호사 Q-S3) / B3=AI 예산 전역 카운터=유료 상한 200명 / 3-tier를 시간지평 기준 재편 제안.
> - **디자인 감사 → 수정** (`01e95300`): **41곳/19파일 카드 보더가 투명**(--pq-hairline=ink-on-ivory를
>   Vantablack 위에 — signals/risk/reports/settings 윤곽선 전부 미표시) → --pq-hairline-ink 일괄 스왑 /
>   랜딩 법적 면책 10.5px→13px(자체 floor) / HomeCard hover slate→bronze / **Source Serif italic 미로드
>   (75곳 합성 오블리크)→진짜 이탤릭** / 신규표면 대비·셸 정합 / 사이드바 그룹 aria-label. LILA BAN 유지 확인.
> - 검증: 프론트 **559/559**(63파일) · 영향권 백엔드 174+ · 백엔드 전체 스위트 → green 후 푸시.
> - **아침 결정 4건**: B2 tier 방향 / CAUS에 sweep 편입+이중화 / B3 per-user 예산 / 그림자색 토큰화 sweep.

> **야간 세션(06-09 밤)**: ① 7문항 리서치 재설계(Steenbarger/Edgewonk/Douglas/Duke 근거) + 단일 SoT
> (`frontend/src/data/pre-trade-questions.ts`, 랜딩 teaser와 drift 차단) + 톤 캘리브레이션 ② 버그헌트
> 4-agent 2-wave: P0 0 / **P1 2 (artifact `$nan` — 수정완료)** / P2 2 (pre-trade row-lock + 수치검증 —
> 수정완료) / 민감영역(billing·NAV버킷팅·이메일 dispatcher 중복발송·dev-login) **플래그만** ③ 전략메모
> `docs/strategy/record-as-spine_2026-06-09.md` + 정직보고 `docs/ops/overnight_report_2026-06-09.md`.
> 7커밋 push 완료(suite 3881 green).
>
> **아침 GO 실행 (Phase 0+1)**:
> - **Phase 0 nav IA 재편**: `terminal-sidebar.tsx`/`bottom-nav.tsx` — **Record 그룹 신설·최상단**
>   (Journal·Pre-Trade(복원, 2026-05-21 제거 번복 per memo §4.1)·Routine), Artifacts=Reports만,
>   **Observe**(=Research 개명+옛 Portfolio 그룹 흡수: Portfolio·Signals·Risk·AI Analysis+hidden 4),
>   System=Alerts·Companion·Profile·Settings. 모바일 primary 4탭은 불변(드로어만 미러).
> - **Phase 1 persona 배선**: 질문 7개는 불변 SoT, persona별 **힌트 1줄만 분기**
>   (`PERSONA_QUESTION_HINTS` — beginner 존댓말/quant 수식/value·income·growth 렌즈, balanced=중립
>   fallback). persona는 **fetch 없이** `cachedPersonaId()`(신규, `lib/cfo/hooks.ts`) = usePersona()의
>   localStorage 캐시 sync read + `_isMock` 가드(오프라인 mock=growth로 오개인화 방지). 모달 테스트의
>   엄격 apiFetch call-count 단언 보존이 이 설계의 이유. 힌트는 mount 후 렌더(hydration 안전).
> - 검증: vitest **557/557**(+9 신규: §17 카피가드+힌트 렌더 4계약) · tsc clean. ⚠️ 로그인 게이트로
>   브라우저 스크린샷은 미실시(렌더 로직은 테스트 커버).
> - 다음 후보: Phase 2(진입 시점 Signal/Risk 스냅샷을 reflection에 동봉) · 홈=오늘의 리뷰(Phase 3) ·
>   플래그 버그 7건(overnight_report §5/§7.2 — NAV 버킷팅·Stripe period_end 우선).
>
> **같은 날 오후 — CEO "스크린샷부터 다해봐" 후속 실행**:
> - **시각검증 완료**: 로컬 dev 서버 + `dev-login`(QA 유저)으로 게이트 돌파 — 사이드바 Record 그룹 /
>   7문항+beginner 힌트(브론즈) / 모바일 드로어 스크린샷 실증. journal 관측라인은 DOM 텍스트로 확정
>   ("진입 시점 관측 · At entry — NEUTRAL 62" ×2 — preview 캡처 파이프라인 버그로 마지막 1장만 흰화면).
> - **/features/* 404 = false alarm**: 어젯밤 dev 서버 인스턴스의 일시 컴파일 상태였음. 새 dev + prod
>   둘 다 전 라우트 200 실측. 코드 무변경.
> - **NAV 버킷팅 fix** (`2610c824`): get_portfolio 합계가 cache-blob currency로 버킷팅 → suffix `is_kr`
>   권위 누적으로 (오염 캐시 시 ~1380x 오산 차단, 형제 endpoint와 동일 컨벤션). +회귀테스트, 75/75.
> - **Stripe period_end fix** (`93c0d946`): API 2025-03-31에서 items로 이동한 `current_period_end` —
>   `_subscription_period_end()` items-first+top-level fallback. +4 단위테스트, 32/32.
> - **Phase 2 완료** (`e5c4e9bc`): `pre_trade_reflections.observed_context_json` (migration **049** +
>   app.py self-heal twin — prod 실제 경로). start_cooldown이 SignalCache signal/score/sector + VIX +
>   1h 변화를 best-effort 수집(§17: rec_*/target 절대 미복사 — 테스트로 고정, corrupt-blob도 write 안
>   막음). journal 카드에 "진입 시점 관측" 1줄. **라이브 E2E 실증**(실 UI 플로우 → NEUTRAL 61.8 저장 →
>   렌더). backend friction 33/33 · frontend 557/557.
> - ⚠️ 발견: `run.py use_reloader=False` — 로컬 백엔드는 코드 변경 자동반영 안 됨(재시작 필요). E2E 중
>   옛 코드로 한 번 헛돈 원인.
>
> **같은 날 저녁 — CEO "다진행해라" (잔여 전부)**:
> - **이메일 drain 중복발송 차단** (`914a48f3`): per-row commit이 FOR UPDATE 락을 풀어 병렬 tick
>   재발송 가능하던 W2-P2 — `services/drain_lock.py` 신설, 3개 dispatcher(onboarding/retention/
>   checkout-followup) tick을 PG advisory lock으로 직렬화(진 쪽은 `skipped_lock` 스킵, SQLite=무조건
>   획득, 락 배관 실패=fail-open). 아키텍처 택1(in-process vs crontab) 없이 양쪽 모두 안전.
> - **방어 hardening 4건** (동일 커밋): dev-login mount가 Railway env 마커에도 거부(FLASK_ENV 무관) /
>   계정삭제 500 detail→예외 타입명만(UniqueViolation 값 노출 차단) / `_serve_stale` KR-code fallback
>   `is_korean` 게이트 / `cost_basis_krw` 저장 buy_fx_rate에 >=900 floor. 영향권 테스트 109 passed.
> - **Phase 3 완료** (`39e4703a`): 홈 데스크 인사 아래 **"오늘의 리뷰 · The Record"** 카드 — 최신
>   reflection 인용 + Phase 2 관측 칩("관측 NEUTRAL 62") + /journal 링크. 빈 journal=null 렌더
>   (신규 유저 홈 불변). dev-login 라이브 검증(어제 E2E reflection이 칩과 함께 렌더) + 카드 테스트 2.
>   §4.3 풀스펙(미결 회상/미러 요약/관측 입력단 프레이밍)은 후속 — 첫 절단면은 회상 카드.
> - **여전히 보류(의도)**: orphan reflection 순서 뒤집기(동작계약 변경 — CEO 리뷰 필요), dev-login
>   기본 tier 강등(premium 의존 E2E 정리 후).

## v62 2026-06-09 — 자율 구조 통합 (CEO "구조 제대로 싹다 잡으라") (⚠️ feature 브랜치 커밋만, **push 안 함**)

> v61에서 리스크로 미뤘던 대규모 구조 통합을 CEO greenlight로 실행. 방법: 정밀 인벤토리(ticker/disclaimer
> agent) → **lead 모든 site 코드 실측 재검증** → 동작보존만, 클러스터별 커밋+전수테스트, 동결파일(quant/*·
> ai/models) 불가침. 상세: `docs/structural_consolidation_2026-06-09.md`.
>
> **✅ 통합 완료 (3 클러스터, 동작보존, 검증)**: ① **fx** `_fx_rate` 7 byte-copy → `fx_service.spot_usdkrw()`
>   단일 SoT(>=900 가드+FALLBACK_USDKRW; 7 wrapper 위임, call-site 불변; engine.py 1350은 frozen이라 유지·문서화).
>   251 test. `19fbc170`. ② **ticker** 7개 private KR판별 재정의(`_is_korean`/`_is_kr`/`_is_kr_ticker`/
>   `DataFetcher.is_korean`) → 캐노니컬 `ticker_normalizer.is_korean_ticker` 위임(모든 입력 동작동일 검증, null-safe
>   개선). KOSDAQ 오라우팅 class 제거. 192 test. `c9f20ed7`. ③ **disclaimer** 16개 byte-동일 법률문구 →
>   `services/legal/disclaimers.py` 4상수(텍스트 0변경; lock test로 정확문구 고정). mirror 5(drift위험)+artifact
>   KR 8+bilingual 4. 669 test. `cc861ac1`.
>
> **✅ ④ _safe_price (CEO "positions 제대로 파악" 푸시로 재검토 → 1차 누락분 발견·수정)** `9cb5dabf`: 1차엔
>   query 줄만 보고 "중복아님" 단정했으나, 진짜 중복은 그 뒤 **가격fetch 로직**이었음. `_safe_price` 5개 byte-동일
>   카피(year_end/risk_board/quarterly/monthly_finance/kpi — `5d hist→last close→isfinite 가드→None`) →
>   `services/artifacts/_pricing.py::safe_last_price` 단일화(=v60 $nan-7곳-수정의 근본원인). 미사용 `import math` 3개 제거. 163 test.
>
> **✅ ⑤ render import helper (전체 dup 스캔으로 추가 발견)** `8c5eb1ad`: _safe_price 누락 후 services/ 전체
>   함수바디 md5 dup 스캔 → 최대 잔여 중복 = `_try_import_weasyprint`(14)+`_try_import_jinja`(18)=**32함수/18파일**
>   (로그문구/레벨만 차이) → `services/artifacts/_render.py` 2함수로 단일화(call-site 불변·동작동일·log WARNING 정규화).
>   AST 기반 제거(변종 바디 일괄), −228줄. 스캔 부산물: _fx_rate/_is_kr "2카피"=내 위임 delegator(정상), _safe_history=context별(유지).
>
> **⛔ 진짜 비중복 (정확히 안 건드림)**: positions **query** 줄 ~30곳(=`.count()` 존재확인/각자 raw Position 로직) ·
>   `_load_positions_with_prices`(SignalCache+KRW정규화 enriched dict=CEO 손대지말란 통화경로) · weekly_memo
>   `_ticker_last_price`(fmp.get_quote) · portfolio_segment `_safe_price_at`(date-window tuple) = 전부 context별 단일 함수.
>   **교훈**: query 줄 중복 플래그가 한 층 아래(연산)의 진짜 중복을 가릴 수 있음 — CEO 재검토 지시가 맞았음.
>
> **🟡 idiom (debt 아님, 미적용)**: inline `is_korean_ticker` `.endswith((.KS,.KQ))` ~60곳 = 동작하는 일관된
>   idiom(재정의와 달리 drift위험 아님). 캐노니컬 존재+SAFE-list 매핑됨 → 클린 mechanical follow-up. money/routing
>   60곳 sweep은 idiom 대비 risk 과다라 미적용.
>
> **검증**: 클러스터별 타겟 green(251/192/669) + 결합 full-suite(본문 §6) · 동결파일 0변경 · FE 무변경(BE-only).

## v61 2026-06-08 — 자율모드 밤샘 버그헌팅 세션3 (6 lane + lead 2 lane, ⚠️ feature 브랜치 커밋만, **push 안 함**)

> CEO "나 자는동안 버그헌팅이랑 구조 다 잡아놔라 자율모드". 6 병렬 헌터(write-path/concurrency/exception/
> migration/structure/frontend) + lead 직접(JSON-NaN/legal-scrub) → **lead 모든 finding 실측+repro 재검증**
> → 안전·비동결만 fix+test, money/legal/frozen/prod-ops/대규모리팩터는 문서화. 상세:
> `docs/overnight_bug_hunt_2026-06-08.md`. **검증: BE full-suite 3861 passed/0 fail(pre-fix는 flaky로 4 fail
> = "baseline green" 오인) · FE tsc0/vitest545.**
>
> **✅ FIXED (검증완료)**: ① **JSON 직렬화 NaN/Inf→null 시스템가드**(`services/json_provider.py`+app.py) —
>   Flask 기본 provider가 invalid JSON(`NaN`/`Infinity`) 방출 → 브라우저 `.json()` throw로 payload 통째 손실.
>   74개 산발 guard + `_finite_floats` 재구현(canonical docstring이 직접 경고한 whack-a-mole)을 단일 경계
>   sanitizer로 대체(+7 test, clean-path 무복사·캐시 불변). ② **flaky 테스트 격리**(conftest autouse) —
>   realtime 싱글톤 KR-health(`_kr_last_fail`)가 테스트간 누수 → data_status overlay가 `is_stale=True` 강제
>   → full-suite 순서에서만 4 fail(**이전 "baseline green 3833"이 가렸던 것**). 싱글톤 reset로 class 제거(probe
>   검증). ③ **PIPA §21 소거갭**(auth.py+pipa_purge.py+test) — `anthropic_usage_log`가 model無+prod FK無(mig042
>   미적용)이라 explicit·FK-sweep 둘다 누락 → 삭제유저 PII 잔존. allowlist sweep(SAVEPOINT격리·funnel_events
>   불가침). ④ **cfo Weekly-Pulse localStorage crash**(P2, hooks.ts) — 구 스키마 `pq_cfo_pulse_v1`→
>   `[...history]` throw(이미 SHIP-BLOCKER 낸 class의 hook 루트 미fix분). `coercePulse` 양 진입점.
>   ⑤ **데드코드**: `cache_service.ca_cache`(미사용 글로벌)·`fmp.normalize_ticker`(데드+footgun: canonical
>   `ticker_normalizer.normalize_ticker`와 동명 역의미·KR→None). ⑥ notification 더블서밋 가드(P3 parity).
>
> **🔴 DOCUMENTED(자동 미적용)**: **[P0] prod alembic_version 032 vs head 048**(migration agent 라이브 prod) —
>   self-heal(`_do_migrations`)로 스키마는 current(parity pass)지만 alembic이 실 migrator 아님 = v44.7 incident
>   class. prod stamp/upgrade는 **불가역 ops, CEO/ops 전용**. money/legal 통합(fx `_fx_rate` 9 byte-copy +
>   1380/1350 상수분기 · disclaimer 8문구 · `is_korean_ticker` 48 inline+7 redef · positions loader ~30 copy =
>   "캐노니컬 존재, 채택이 갭"). pykrx 데드스텁이 LIVE `/alt-data/kr/*` 빈데이터 서빙(제품결정). 마이그 004/005
>   JSONB·016-019 BigInteger SQLite 비replay(latent: prod=PG/test=create_all). 통화 KRW/USD 혼합 = CEO LEAVE IT
>   유지([[feedback_currency_separate]]).
>
> **✅ CLEAN(증거, 6 lane)**: write-path 128 handler IDOR/검증/mass-assign/race **0**(예외적 하드닝) · concurrency
>   P0/P1 0(EGW02004 self-heal depth-2 bounded·token-mgr 락 정상·scheduler max_instances=1) · exception(framework
>   글로벌핸들러로 stack-leak/HTML-into-json 0·user int/float 전부 400가드) · migration head 단일 048 linear
>   (data-loss 0) · frontend SSE teardown·timer/observer cleanup·mutation 더블서밋 가드·format.ts NaN 가드 존재.

## v60 2026-06-07 — CEO 라이브 신고 fix 2건 + 자율 버그헌팅 세션 2 (⚠️ feature 브랜치 커밋만, **push 안 함**)

> CEO 라이브 사용 중 신고 2건 → fix → "자율모드로 밤새 버그헌팅, 모든 케이스, 버그 없게". 상세:
> `docs/overnight_bug_hunt_2026-06-07_session2.md`. baseline green(pytest 3833 / vitest 545 / tsc 0).
>
> **✅ FIXED (검증완료, 커밋 `64546d4a` + 후속)**: ① **온보딩 broker 데스크탑 레이아웃 붕괴** — `(auth)/layout.tsx`
>   가 모든 자식을 `max-w-sm`(384px) 폼 셸에 가둠. 온보딩(broker/질문지)은 자체 풀폭 앱셸(max-w-3xl/lg)이라
>   md+ 에서 `md:grid-cols-2` 가 384px 안에서 발동→카드 찌부·한글 세로·뱃지 겹침. 좁은 셸을 login/signup
>   레이아웃으로 이전, 온보딩 풀폭 해방(login/signup V2 는 pq-auth-shell fixed full-bleed 라 무영향, 실측 확인).
>   ② **저품질 동전던지기 Q14 제거**(CEO "이딴 질문 빼라") — 20→19문항. 크로스-스택(프론트 data slice 19→18 +
>   risk 정규화 FE 5.5→4.5/BE 4.0→3.0 + loss_aversion 파생으로 출력스키마 불변 + 테스트 fixture). 배포경계
>   안전(step 항상 0 초기화). ③ **아티팩트/상세 `$nan` 방어**(Lane E A1/B2) — `_safe_price` NaN 미가드 →
>   `or avg_cost` fallback defeated → 유료 PDF `$nan`. 7함수 non-finite→None + fetcher 상세가드 `cur != cur`.
>
> **🟠 CEO 결정(자동 미적용)**: **통화 KRW/USD 혼합**([[feedback_currency_separate]] "냅두라 몇번말하노") —
>   신규 열거 F1 `simulate.py` ×5 엔드포인트 raw-mix(가중치 왜곡) + F2 `credit_rating` raw-mix. 기존 known
>   B2(twin)/B3(portfolio_analytics)와 함께 **통화-정책 일괄 결정** 안건. **절대 FX-환산 합산 금지**.
>
> **✅ CLEAN(증거, 8 lane)**: 캐시 cross-user(Pattern6) 0 · auth/세션/OAuth/리다이렉트 0 · 법적 라벨(BUY/SELL/HOLD·추천) 0 ·
>   티어게이팅(Pro6/Prem9/free3) · FX silent-1.0 없음 · KR 티커 normalize 2,770엔트리 · **대시보드 코어 29 엔드포인트 신규유저
>   실측 29/29 `<500`** · SSE cross-user 0 + 스트림 auth ✓ + PWA SW per-user 캐시 evict ✓. LOW 2(배포후 stale-bundle race
>   `install-prompt.tsx`·CLEAR_API_CACHE old-SW) = 문서화. §101 AI 텍스트 = 라우트 레이어 scrub(10 routes+decorator) 확인.

## v59 2026-06-07 — 자율모드 새벽 버그헌팅 (7 정적 헌터 + lead 실측 재검증) (⚠️ feature 브랜치 커밋만, **push 안 함**)

> CEO: "자율모드로 버그 다잡고 모든 가능한 케이스들 다 확인 … 구조잡고 나자러가게". browser 불가(CEO 세션
> 부재)라 정적+prod-API+테스트 헌팅. **baseline green 고정**(pytest 3811 / vitest 541 / tsc 0) → 7 lane 병렬 →
> **lead 가 모든 finding 실측 재검증**(v58 verify-gap 교훈) → 안전·비동결만 fix+test, 동결·머니매스·판단은 패치까지
> 작성해 문서화. 상세: `docs/overnight_bug_hunt_2026-06-07.md`.
>
> **✅ FIXED (검증완료)**: ① KOSDAQ 거래소 오라우팅 — `fetcher.quick_lookup` 가 6자리 코드에 무조건 `.KS` →
>   KOSDAQ(035760 등)가 KOSPI로 조회돼 **다른 종목 가격** 반환. `normalize_ticker()`로 교체(+test). ② Backtester
>   0-가격 바(KR 거래정지일) 나눗셈 가드 3곳(bh_return/mom20/daily_rets) — 무가드시 백테스트 None 붕괴/inf JSON
>   (backtester.py 비동결, +test). ③ 로그아웃 SWR 인메모리 캐시 미삭제 → 공용기기 cross-user 첫페인트 노출
>   (auth.tsx, global mutate evict). 회귀: 신규 7 test green + 타겟 848 passed + tsc0/vitest541.
>
> **🟠 CEO 결정 필요 (패치 작성됨, 자율 미적용)**: B1 동결 퀀트 crash 4건(StatArb std0 / portfolio cummax NaN /
>   AnchoringBias 0-price / GKYZ log0 — 전부 degenerate 입력, Iron Rule §1 승인 필요). B2 **AI Twin KRW/USD
>   통화혼재**(twin_runner write-path, `RUN_SCHEDULER=1`+활성트윈 시 LIVE — v58이 deferred한 그 버그). ⚠️
>   **FX-환산 금지**([[feedback_currency_separate]] — CEO "krw usd 냅두라 몇번말하노"): 해법은 KR제외(권장) or
>   통화별 cash 분리, **절대 환산해 합치기 아님**. B3 portfolio_analytics 통화 raw 합산도 동일 — 통화별 버킷 분리(환산X).
>
> **🟡 문서화**: billing cancel/refund 404(결제 전 SHIP-BLOCKER) · S&P/Nasdaq=SPY/QQQ ETF proxy 표기(디스클로저
>   칩 렌더 확인) · .env.production V2 플래그 false footgun · chat-stream 청크 scrub(AI_CHAT_ENABLED=0 무surface) 등.
>
> **✅ CLEAN(증거기반)**: 캐시 cross-user(Pattern6) 0건 · 인증/티어/IDOR/webhook/OAuth state 0건.

## v58 2026-06-06 — CEO UI 지시 4건 + 새벽 버그헌팅(5 agent) (✅ 커밋 4 · push · 배포)

> CEO: 포트폴리오 가짜데이터→"모으는중"+기간 1주/4주/8주 / methodology 공개페이지+사이드바 제거 /
> 랜딩 한글폰트 / "새벽동안 버그헌팅 모든 경우의 수 + 유저모방 자동화 점검". → UI 4건 구현 + 5 agent
> 헌팅 → **lead 실측 재검증** → 명확건 fix·배포, 나머지 문서화. 검증: tsc 0 · vitest 541 ·
> pytest(타겟) green · **next build exit 0** · pre-push 5가드 green. 커밋 4 (`ef2bedc2`→`67a4d966`),
> feat+main FF push, **베타게이트 유지**.
>
> - **U2/U3 포트폴리오 equity**: 기간 **1주/4주/8주**(5d/1mo/2mo, 백엔드 portfolio.py+fmp.py+
>   **kis_market_adapter.py** 2mo=60d) default 4주. 데이터 없으면 "기록이 쌓이는 중"/"모으는 중"(합성
>   0). ※ 백엔드 history는 이미 REAL NAV만 plot(가짜 0) — 진짜 원인은 월단위 윈도우라 신규유저 2주
>   데이터가 우측 몰림/misleading → 주단위로 해소.
> - **U4 methodology**: 공개 `app/methodology/page.tsx`(static·public-safe — gated academic_source
>   dump 제외=METHODOLOGY_PUBLIC/Q-DT4 유지) 신설, **dashboard 라우트 삭제**, 사이드바(terminal+bottom)
>   에서 제거. 로그인 게이트 아님.
> - **U1 hero 한글폰트**: Playfair에 한글 글리프 없어 system serif fallback("개구림") → `pq-hero-h1`
>   스택에 Pretendard 삽입(한글=Pretendard·Latin=Playfair, per-glyph). ⚠️ **시각 미확인**(베타게이트+
>   무브라우저) — CEO 의도 섹션이 hero 아니면 재지정 필요.
> - **새벽 헌팅 fix(배포)**: **weekly-memo 전유저 크래시 가드**(`data.trajectory` 없으면 EmptyState —
>   "REPORT REFRESHING"/서버에러 해소) · **KR 보유종목 detail 게이트**(normalizeTicker 양측, 005930.KS↔005930).
> - **유저모방 자동화(N2)**: AI Twin = 유저 페르소나 모방 paper 거래. ✅ **실주문 차단**(KIS order
>   permanently disabled) · paper-only 강제 · 멱등(max_instances=1/workers=1) · §101 OK. 이메일 자동화
>   5종 전부 flag-OFF + is_simulated 필터.
>
> ### 🟠 carry-over (문서화·미fix — CEO 검토/판단 필요)
> - **G: twin_runner.py 쓰기경로 KR 통화혼재**(`_close_check`:293-296, buy:361-376) + `twin_reporter.py`:66-77 —
>   B5는 routes/twin.py 읽기경로만 fix. 쓰기경로는 KRW proceeds를 USD cash에 raw 가산(latent: twin paper가
>   KR 보유 시). 같은 Pattern-7. **money-math+DB write라 신중 fix 필요**(추측 금지로 보류).
> - **F: V1 home naked ticker**(`home/_v1/page-v1.tsx`:318/410/488/921 `{r.ticker}` + `candlestick-chart.tsx`:380) +
>   ⚠️ **`.env.production NEXT_PUBLIC_HOME_V2=false`** ↔ CLAUDE.md "V2 prod true" **모순** → **Vercel env 확인
>   필요**(V1이 prod active면 naked ticker 라이브 노출). normalizeTicker fix는 V1/V2 양쪽 안전.
> - **MED**: equity NAV 첫호출 divergence ~16.6%(record_today_snapshot+RT race) · 혼합포트 KOSPI200 벤치마크
>   (`any(.KS)`, 비중기반 아님) · todayPnlUsd=0(US change_pct overlay 누락) · weekly-memo artifact raw .KS
>   (백엔드 정규화 필요) · KOSPI 8,160 의심값(sanitize 범위 광범) · risk_quant period whitelist 부재.
> - 상세 + 위치: `qa_bug_log.md` v58 섹션.

---

## v57 2026-06-05 — 자율모드: 버그헌팅 전수 + legal 결론 + 임베디드 카피 감사 (✅ 커밋·push·배포)

> CEO "자율모드 최고판단 다 하라(베타게이트 해제만 제외)" + "예산/메모 최신화" + "박혀있던
> 문구 싹다 전수조사→최신동향 파악". → 9 agent 병렬(버그헌팅 6 + 카피감사 3) → **모든 finding
> lead 가 코드 실측 재검증**(에이전트 주장 정정 포함). **빌드 green: pytest 3810 passed/0fail
> (1150s) · tsc 0 · vitest 541.** 버그 8건 fix + "58→40" 오버클레임 정정, 5건 근거 문서화 보류.
>
> - **법적 결론**: 무료 출시 = **코드 GO**. 유일 hard blocker = **PIPA §30** 처리방침/약관 "초안"
>   라벨 라이브 게시(내용 완성형·라벨만 제거하면 됨·과태료 최대 3천만 형사X). §101 = 무료(대가없음)
>   →면제 LOW. **"초안 제거 + 베타게이트 해제"는 CEO 지시로 보류**(공개출시 = 변호사 게이트와 한 쌍).
>   무료상담 패킷 `docs/legal/상담A·B·실행계획` 준비완료.
> - **버그 fix 8**: B1 `/api/*` 4xx JSON(HTML→프론트 .json() silent 실패) · B2 regime/turnover/
>   ledger NaN 차단(_finite_floats) · B5 AI Twin paper-side USD 정규화(₩+$ raw 합산 Pattern-7,
>   cash=$10k base) · B6 Artifact 5종 TradeHistory 혼합통화 정규화(year_end/quarterly/brag/
>   monthly_brag/kpi, +회귀6) · B7 FX fallback 단일상수(1370/1380→`FALLBACK_USDKRW`) · B8
>   legal_filter↔forbidden_terms core-directive 파리티 테스트 · B4 /pre-trade 면책 coaching 매핑 ·
>   B13 what-if raw hex→`var(--down)` 토큰.
> - **카피 감사(3 agent)**: "58 quant models" = 오버클레임(SoT `model_catalog.py` assert==40,
>   features 페이지는 이미 40 = 내부 모순) → **6곳 58→40 정정**(표시광고법 §3, 2026 시행령 "외부
>   자문 감경 삭제"로 미실증 수치 직격 — 시의적절). **lead 정정**: discover 배너 누락=FALSE
>   POSITIVE(layout PATH_TO_TYPE 매핑 존재) · seven-layer 가독성=비활성 v1만(DOWNGRADE).
> - **보류(근거 문서화·추측 fix 금지)**: B3 iOS `window.confirm` 무음(실기기 검증·invasive) · B9
>   consent 컬럼(net-safe·§50 Q-S1 lawyer-gated) · B10 랜딩 indices null(코드버그 아님·cache-only
>   설계·prod 로그 의존) · B11 SENDGRID env(Railway·CEO) · B12 TierGate /pricing(Stage1 전용) ·
>   paper-trading 페이지 §101 어휘(CEO 결정) · 17vs18 artifacts(canonical 재조정) · §31 이메일템플릿
>   갭(brag_celebration/dd_checklist, 변호사 검토).
> - **CLEAN 확인(실측)**: cross-user PII 누수 0(cache 198참조) · 동결파일 위반 0 · FX precedent 3종
>   (portfolio_history/risk_summary/build_context) fix 유지 · BUY/SELL 0 · violet 0 · naked ticker 0.
> - **메모리 최신화**: `qa_bug_log.md`(v57 전수) · `finance_budget.md`(이번 세션 0원) ·
>   `legal_copy_audit_2026-06-05.md`(신규).
> - **검증**: pytest 3810/0fail · tsc 0 · vitest 541. 스코프드 커밋 3(backend/frontend/docs) → main
>   FF → prod 배포. **베타게이트 유지(공개 노출 0)**.

---

## v56.1 2026-06-04 — push + prod 배포 (2회) + Stripe 전면 비활성화 (✅ 완료)

> CEO "푸시해라"·"stripe 비활성화 모든 부분에서(무료출시)" → **2회 prod 배포 전부
> health green**. 1차 `bcddc73a`(overnight: crypto/behavior/privacy). 2차
> `bbf4b073`(Stripe 마스터 kill-switch + nav flake fix). 각 pre-push 가드 5단계 green.
>
> - **Stripe 전면 OFF**(삭제 아닌 게이트, Stage1 부활 보존): `STRIPE_ENABLED` 마스터
>   플래그 + `billing_bp.before_request` 가 결제/상태변경 라우트 전부 503(기존
>   비게이트 **webhook 포함**). read-only `/subscription` + 공개 `/availability`
>   EXEMPT(무료유저 본인 tier 조회 + off-state 표시). CSP stripe 도메인 제거. **prod
>   검증**: `/api/billing/availability` → `available:false`. 이미 OFF였던 것:
>   pricing 307 redirect · checkout/portal 503 · 업셀 진입점 숨김 · d7 메일 게이트.
> - **nav_snapshot KST-morning flake fix**(test-only): record_today_snapshot 가 UTC
>   date, 테스트는 local date.today() → KST 00–09시 매일 충돌 fail. UTC 통일. full
>   suite 3791 green 복구. **prod equity curve 무영향**(이미 UTC 일관, 과거행 무손상).
> - 검증: pytest 3791/0fail · tsc 0 · vitest 541 · billing 81.
> - **출시 실게이트 = 외부 변호사뿐**(약관 v2 §13 등록번호 + 처리방침 게시). 코드 GO.

---

## v56 2026-06-03 — 자율 버그헌팅 + legal 전수 + 미커밋 WIP 마감 (✅ 로컬커밋 3 → push·배포됨)

> **결론**: CEO "자율모드 버그헌팅+구조+출시 미완성 100%+legal 싹다" 취침 위임.
> **빌드 100% green 실측**: 백엔드 **pytest 3791 passed / 0 fail** (608s) + 프론트
> **tsc 0 / vitest 541**. 4 agent 병렬 헌팅(WIP correctness / crypto 보안 / FX 일관성 /
> legal-kr-fintech) → 모든 finding 을 lead 가 코드 실측 재검증(추측·forward 금지).
> **로컬 커밋 3건**(`319cdbca` crypto / `a97c517e` behavior / `555e2bbc` chore),
> **미푸시**(feedback_push_workflow 🟥 — CEO 명시 push 지시 없었음). 0원.
>
> **출시 = 무료(Stage 0) code-side GO** (legal-kr-fintech 판정): §101 면제 4요건
> 충족 / R7 KIS 마케팅카피 게이트 clean(금지표현 0) / 금지어 유저표면 0. **진짜
> 남은 게이트 = 외부 변호사뿐**: 약관 v2 §13 유사투자자문 등록번호 공란 + 처리방침
> v2 게시 검토(핀테크 상담소 무료 1.5h). **코드가 막는 출시 BLOCKER 없음.**
>
> ### 처리 (미커밋 WIP = "미완성 부분" 검증+마감 + 헌팅 발견 fix)
> - **미커밋 WIP 커밋**: 행동거울 correctness — FIFO 동일타임스탬프 결정성 +
>   같은날 동일종목 2매수 collision 으로 open-share 누락 fix / concentration FX
>   정규화 / persona-benchmark sub-score strip / 5거울 DOM 렌더 테스트(옛
>   "16/18 render test 누락" carry-over 해소). bug-hunter 적대검증 → WIP clean.
> - **FX-consistency Pattern 7 쌍둥이 fix**: concentration_mirror 가 고친 raw
>   cross-currency `shares*avg_cost` 합산 버그가 `scorer._position_sizing_subscore`
>   에도 동일 존재(group_benchmark 코호트 median 으로 전파). 공유 헬퍼
>   `fx_service.cost_basis_krw()` 신설 → 둘 다 경유(영구 drift 차단). scorer 는
>   DEPRECATED지만 group_benchmark 가 live 호출 → 실수정.
> - **crypto 데이터안전**: keyring 복호화 실패 시 silent `""`(→다음 write 시 원문
>   영구 덮어쓰기) 를 키버전부재(operator env-drift)=fail-loud / 변조=blank 로 분리.
>   latent(아직 v2 키 없음)지만 첫 로테이션 전 차단.
> - **privacy 게이트**: persona-benchmark API sub-score 5개 strip(점수화폐기+§3) +
>   common_mistakes count 재식별 floor `max(2, n//10)`(소규모 베타 코호트 PIPA §23).
> - +회귀테스트 6건. 상세 메모리 `session_2026-06-03-overnight.md`.
>
> ### ⚠️ CEO 액션 (코드 아님)
> 1. **push 결정**: 위 3커밋 검토 후 `git push origin feat/data-storage-trust`(또는
>    main FF 병합). 검증 끝남(3791/541/tsc0). 미푸시 사유 = 명시 push 지시 부재.
> 2. **출시 실게이트 = 외부 변호사**: 약관 v2 §13 등록번호 + 처리방침 v2(핀테크상담소).
>    이거 풀리면 베타게이트(Vercel 307) 내리고 무료 출시 가능.
> 3. legal carry-over(BLOCKER 아님): insider-mirror "매수/매도 공시"→"취득" 관찰어화
>    (LOW 허용) / comparison_to_all 미렌더 필드(향후 렌더 시 §3 재검수).

---


---

## 과거 이력 (v55 이하)

2026-08-30 분리 → `docs/archive/HANDOVER-history-v55-and-older.md`
