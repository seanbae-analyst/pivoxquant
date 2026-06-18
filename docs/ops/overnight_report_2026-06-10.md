# 🌙 야간 자율 세션 리포트 — 2026-06-10 (2탄)

> 대상: 배상현(CEO) · 작성: Claude (자율모드) · **정직 보고 모드**
> 지시: "자율모드로 버그헌팅 + 사업모델·디자인 감사 돌려서 깨지는 부분 다 확인 +
> 구조도 잘 잡고 + 가상유저 20명 테스트 + 옛날에 명령 내린 거 되고 있는지 확인 +
> 새벽 동안 다 해놔라."

---

## TL;DR (30초)

| 지시 | 결과 |
|---|---|
| "옛날 명령" 확인 | ✅ **CAUS — 돌아는 감, 반쪽** (§1) |
| 가상유저 20명 테스트 | ✅ 신규 sweep 하네스 — **336 호출 0 findings ×2회** (§2) |
| 버그헌팅 (wave 3) | ✅ 12건 발견 → **10건 수정** (P1 2건 포함), 2건 보류 (§3) |
| 사업모델 감사 | ✅ **B2: 가격표↔코드 9건 불일치** = 미인지 출시 BLOCKER (§4) |
| 디자인 감사 | ✅ **41곳 보더 투명** 등 10건 → 전부/대부분 수정 (§5) |
| 구조 | ✅ `safe_cache_blob` SoT 신설(13곳 통합) + sweep 하네스 영구화 (§6) |

**커밋 5개** (wave-3 backend / frontend / design / qa-harness / docs) — 백엔드 전체
스위트 green 확인 후 푸시. 프론트 **559/559** 확정.

---

## 1. "옛날에 명령 내린 것" = CAUS — 정직한 실태

**돌아는 갑니다. 단, 당신이 원한 것의 반쪽입니다.**
- 매일 03:00 fire, 리포트 16개 누적 (`docs/qa/auto-sim-reports/`), 오늘 새벽도 실행
  ("Day 7 시나리오, findings 0").
- **그러나**: ① 하루에 **유저 1명**(sim1~10 로테이션) × 시나리오 1개 — "20명"이 아님
  ② **갭 많음**: 5-18/19, 5-24, 5-26, 5-29~31, **6-03~6-08 6일 연속** 미발화
  ③ 원래 launchd는 2026-05-28 RETIRED — 지금은 Claude 스케줄러가 fire (맥이 꺼져 있으면 미발화 — 갭의 원인).

→ 그래서 §2의 20-유저 sweep을 **별도 신규 하네스**로 만들었습니다 (CAUS 보완, 대체 아님).

## 2. 가상유저 20명 — 신규 sweep 하네스 (재사용 가능)

`scripts/qa/virtual_user_sweep.py` — 8 페르소나 × free/pro/premium × 8 포트폴리오
유형(빈/KR만/US만/혼합/소수점주/99.9만주/BRK-A 1주/KOSDAQ). 각 유저: 로그인 → 포지션
구축 → **7문항 deposition→proceed** → journal → persona/profile/signals/alerts/
watchlist/risk 전 표면. 검사: 5xx·NaN/Infinity·NAV suffix-버킷 정합·journal 무결성.
in-process(SQLite 격리) — 결정적, ₩0, 수 초.

**결과: 336 호출, findings 0 — 2회 모두 클린.** (1차 실행의 전원 403은 하네스의 CSRF
계약 오류였고 — 역으로 CSRF 방어가 작동한다는 증거. 수정 후 클린.)
실행법: `./venv/bin/python scripts/qa/virtual_user_sweep.py --users 20`

## 3. 버그헌팅 wave 3 — 12건 발견, 10건 수정

> 미커버 영역(behavior/twin/profile 서비스, 잔여 routes, frontend lib/hooks, sw.js) 대상.
> **P0 0건.** behavior mirrors·fifo·persona classifier·format.ts 등은 명시적으로 clean.

**수정 완료 (`08c51390`, `c05e4915`):**
- **[P1] NAV alias 버킷팅** — 어제 고친 get_portfolio와 **같은 버그가 v2 프론트가 실제
  쓰는 `/api/portfolio/positions`에 남아있었음** (내 어제 커밋 메시지의 "형제는 이미
  suffix" 주장이 이 totals 블록엔 틀렸던 것 — 정직 인정). suffix 버킷으로 + 회귀 테스트.
- **[P1] signal_detail 15s 타임아웃이 가짜** — `with ThreadPoolExecutor` exit이
  wait=True라 행이 그대로 전파 (실행 검증됨). `shutdown(wait=False)` detach로 진짜 15s.
- **[P2] twin 주간 수익률** — SELL proceeds를 분모에 합산(+₩$ 혼합 raw-sum) →
  같은 주 $1,000→$1,100 왕복이 +4.76%로 표시. **realized P&L / realized cost basis**
  (KRW 정규화)로 — twin 쪽과 동일 척도. ⚠️ 에이전트 제안(BUY-only 분모)은 주간
  시맨틱에 회귀를 만들어 (SELL-only 주가 전부 None) **수정해서 적용** — 과거 persist된
  주간 rows는 옛 수학(문서화된 drift, 재계산 안 함).
- **[P2] risk_summary literal NaN** — 거래정지(평평한) 종목이 corr를 NaN으로 → 유효하지
  않은 JSON → /risk 폴링 전체 깨짐. isfinite 가드.
- **[P2] SW 캐시 cross-user 창** — `/api/profile` SWR prefix가 **PIPA 전체 개인정보
  export까지 60분 디스크 캐시** + 로그아웃 없이 계정 전환 시 이전 유저 응답 노출 가능.
  export는 network-only로, auth는 user id 변경 감지 시 SW 캐시 클리어 (OAuth 풀
  리다이렉트는 기존 클리어 경로를 안 탔음).
- **[P3 ×5]** corrupt 캐시 1행이 watchlist/signals/alerts/portfolio 응답 전체를 500
  → `safe_cache_blob()` SoT 신설, 13곳 통합 / $0 STOP_LOSS 오발 차단 / refresh
  `"price": null` TypeError / detail watchlist 비교 normalize / watchlist GET N+1 배치.

**보류 (의도):** SSE slot leak (좁은 윈도우 + call_on_close 재설계 필요),
rolling_metrics 180× FIFO 성능 (동작 영향 가능, 베타 규모에선 미체감).

## 4. 사업모델 감사 — "깨지는 부분" (메모: docs/strategy/business_model_audit_2026-06-10.md)

| # | Break | 성격 |
|---|---|---|
| **B1** 🔴 | §101 ② "매월 청구 금지" vs 월구독 ₩9,900/19,900 — 수익모델 자체의 법적 단일 실패점 | **변호사 Q7/Q-S3만이 답** (코드 불가) |
| **B2** 🔴 | **가격표↔코드 9건 불일치** — Pro로 파는 12개 중 6개(Risk Board·Insider·Dividend·Quarterly·Self-Audit·Segment)가 백엔드에선 **Premium 게이트** (내가 grep으로 실측 확정). 역으로 Premium으로 광고한 3개(Credit Rating·Burn Rate·KPI)는 Pro도 받음 | **결제 켜는 순간 첫 Pro 유저부터 깨짐.** 표시광고법 리스크. 어느 쪽으로 통일할지 = **가격 결정이라 당신 몫** — 밤에 안 건드림 |
| B3 🟠 | AI 예산이 전역 카운터 (weekly_memo 200/day 등) = **유료 유저 상한 200명** | per-user 전환 (코드, 결제 전까지 여유) |
| B4 🟠 | KIS 시세 재배포 (기존 R7 이슈 재확인) | 변호사/벤더 |
| 비판 | 3-tier 컷이 "기능 가치"가 아니라 "아티팩트 개수" 기준 — B2의 근본 원인. **시간지평 기준 재편** 제안 (Pro=주간/이벤트, Premium=분기/연) | 전략 결정 |

## 5. 디자인 감사 — 가장 충격적인 발견

**[P1] 41곳/19파일의 카드 보더가 수학적으로 투명했음** — `--pq-hairline`은
ink-on-ivory 토큰(rgba(10,10,10,.08))인데 Vantablack 위에 칠해져 **signals/risk/
reports/settings의 카드 윤곽선이 전부 안 보이는 채로 prod에 떠 있었음** (hover 시
브론즈가 "무에서" 튀어나오던 게 증거). 올바른 토큰(`--pq-hairline-ink`)으로 41곳 일괄
스왑 (`01e95300`).

그 외 수정: 랜딩 법적 면책이 10.5px(자체 13px floor 위반 — W19 sweep이 기계적으로
축소했던 것)→13px / HomeCard hover가 light-theme slate→브론즈 / **Source Serif 4
italic이 아예 로드 안 돼 75곳이 합성 오블리크**→진짜 이탤릭 로드 / 신규 표면 대비
(persona 힌트 .66→.85 등) / TodaysReviewCard를 HomeCard 셸에 정합 / 사이드바 그룹이
스크린리더에 안 보이던 것(aria-label).
**Clean 확인**: LILA BAN(보라) 유지, Inter 0, 5-24 가격색 반전 미재발.
보류: #8B6F47 그림자 색 토큰화(~50곳, 별도 sweep 권장), pctColor 0-케이스 4곳.

## 6. 구조

- `services/cache_service.safe_cache_blob()` — 13곳 중복 parse SoT 통합 (v62 철학 연장)
- sweep 하네스 영구화 (`scripts/qa/`) — CAUS와 상호보완 구도 정리
- 디자인 토큰 정합 (hairline 41곳이 사실상 구조 정리)

## 7. 검증 & 커밋

- 프론트 **559/559** (63파일) / 영향권 백엔드 174+ passed / sweep 336 호출 0 findings ×2
- 백엔드 **전체 스위트 실행 중** — green 확인 후 푸시 (결과는 HANDOVER/푸시 로그에)
- 커밋: `2d28fd14`(sweep) `08c51390`(backend fixes) `c05e4915`(frontend fixes)
  `01e95300`(design) `785d438e`(docs)

## 8. 아침에 당신이 결정할 것

1. **B2 — tier 통일 방향**: 코드를 가격표에 맞추나(6개 Pro로 하향 = 가치 증가, 마진
   영향) / 가격표를 코드에 맞추나(카피 수정 = 가장 빠름). 결정 주시면 정합성 회귀
   테스트까지 한 번에.
2. **CAUS 보강**: 매일 20-유저 sweep을 CAUS에 편입? (cron 1줄 — sweep은 ₩0/수 초)
   + 6일 갭 재발 방지(스케줄 이중화)?
3. B3 per-user 예산 전환 시점 (결제 ON 전 필수).
4. 디자인 보류분: 그림자 색 토큰화 sweep GO?
