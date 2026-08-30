# 야간 자율 버그헌팅 리포트 — 2026-07-02

대상 3개 레포(pivoxquant / pivox-brief / dataready)에 버그헌터 10개 병렬 투입.
발견 ~35건. 이 중 **확실하고 위험이 낮은 8건은 수정 + 로컬 검증 완료**(전부 GREEN).
나머지는 아래에 근본원인·수정방향과 함께 문서화 — 결제/원장/재시도 의미를 바꾸는
것들은 야간에 blind fix하지 않고 CEO 승인 대기로 남김.

> ⚠️ 커밋/푸시 안 함. 전부 working-tree 편집만. 각 레포 브랜치:
> pivoxquant=`fix/email-provider-retry`, pivox-brief=`main`, dataready=`main`.

---

## ✅ 수정 완료 (8건, 검증됨)

| # | 레포 | 심각도 | 버그 | 수정 | 검증 |
|---|------|--------|------|------|------|
| 1 | pivoxquant | HIGH(sec) | `AUTOPILOT_BACKLOG.md`/`BUG_SWEEP_*.md`에 베타 비번 평문 노출 + secret-leak pytest RED | 값을 placeholder로 마스킹 | `test_pivoxaudit_secret_leak.py` 12 passed |
| 2 | pivoxquant | P1 | `/settings` 페이지가 founding_lifetime/premium_plus를 "Free"로 강등 → Billing/Cancel/영수증 UI 은닉 | tier 매핑에 두 티어 추가 (reports의 toUiTier와 동일) | tsc clean, tier 테스트 11 passed |
| 3 | pivoxquant | P1 | `/risk` VaR/ES 게이지 100배 과장 (백엔드 이미 percent인데 `\|x\|≤1?×100` 재곱) | 재곱 휴리스틱 제거, percent로 직접 사용 | tsc clean, 백엔드 계약 확인 |
| 4 | pivoxquant | P2 | `POST /api/watchlist` ticker 길이 미검증 (SQLite 500자 저장 / Postgres 500) | portfolio.py SEC-004 패턴 이식 (>20자 → 400) | watchlist 테스트 17 passed |
| 5 | pivox-brief | **P0** | 공개 홈페이지 stored XSS — anon key로 Supabase 설정 덮어써서 `custom` 티커에 HTML 주입 | 이중방어: `_validate` ticker 문자셋 제한 + `_esc` 따옴표 이스케이프(brief_home+brief_html) | 악성 payload 차단 확인, 126 passed |
| 6 | dataready | **CRITICAL** | xlsx CLI 완전 파괴 (`XLSX.readFile is not a function`) + parse/CLI 에러핸들링 부재 | default import 교체 + cli.mjs try/catch (ENOENT/EACCES/corrupt) | xlsx 스코어링 정상, 에러 메시지 정상, 게이트 green |
| 7 | dataready | **CRITICAL** | sentinel 토큰이 20%+ 결측과 충돌 시 감지·정제 모두 무력화 (`else if` 체인) → "cleaned" CSV에 N/A/NULL 잔존 | sentinel 체크를 독립 `if`로 분리 | N/A/NULL 정제 확인, validate+sim green |
| 8 | dataready | **P0** | `serve.mjs` path traversal — sibling 디렉토리 프리픽스 우회로 ROOT 밖 파일 읽기 | `path.resolve` + `ROOT + path.sep` 경계 검사 | traversal 403, 정상 200 |

---

## ⏳ 미수정 — CEO 승인/판단 필요 (결제·원장·인프라 의존)

### pivoxquant

- **[CRITICAL] checkout 팔로업 이메일 영구 드롭** — `scripts/nightly/checkout_followup_dispatcher.py:179-185`.
  이메일 provider(SendGrid+Brevo) 동시 장애 시 결제이탈 재유도 메일이 단 1 tick만에
  `provider_failed`로 영구 종료. PR #529가 onboarding/retention 큐에 넣은 3일 retry 로직이
  이 큐만 누락. origin/main에도 동일 존재. **수정방향**: `services/billing_followup.py`가
  provider outage 여부를 노출 + dispatcher가 `_PROVIDER_RETRY_WINDOW` 적용. (pytest 재현 완료)
- ~~**[P0] AI Twin FX 원장 손상**~~ → **✅ 2026-07-03 수정 완료.** `services/twin/twin_runner.py`.
  실제 원인: 현금 차감은 정확했고 **포지션 주식 수가 1380배 적게 기록**되어 KR 보유 시
  `twin_lifetime_pct`가 ~-100%로 표시. 수정: `_price_to_usd()` 헬퍼로 매수(`_score_universe`)·
  청산(`_close_check`) 두 경계에서 KRW→USD 변환 + `reconcile_legacy_krw_positions()`(idempotent)로
  기존 오염 포지션 복구(shares×spot / avg_cost÷spot, USD 원가 불변). 회귀 테스트 4개 신설
  (`tests/test_twin_fx.py`). 검증: twin 31 passed, ruff clean. 커밋 안 함(working-tree).
  ⚠️ prod 기존 데이터 복구는 `reconcile_legacy_krw_positions(dry_run=False)`를 Railway
  DATABASE_URL로 1회 실행 필요(별도 CEO 액션).
- **[HIGH] 이메일 4xx→provider_unavailable 오분류** — `services/email/sender.py:462-518`.
  영구적 4xx(미인증 발신자 등)를 일시 outage로 처리해 3일간 무의미 재시도 → 무료 쿼터 낭비.
  **수정방향**: SDK 예외 타입(BadRequest vs Upstream/RateLimit) 구분해 4xx는 즉시 skip.
- **[P1] `/api/portfolio/analytics` FX raw-sum** — KRW+USD market_value 원시 합산으로 섹터
  가중치·Sharpe 왜곡. 현재 프론트 미사용(dead) → 긴급도 낮으나 부활 시 즉시 버그.
- **[MEDIUM] `routes/share.py:138` total_value_usd가 KR 포지션 제외** (변환 없이 누락).
- **[MEDIUM] Brevo webhook 미이식** — SendGrid→Brevo 전환 시 bounce/spam 웹훅 서명검증
  라우트 미생성. §50 opt-out 자동화가 실제 발신 provider에서 미작동 가능.
- **[MEDIUM/P3] pre_trade·quant_composer tier 게이트 부재** — 결제 비활성 상태라 "의도된 무료
  개방"인지 "게이트 누락"인지 코드만으로 판별 불가. 결제 활성화 시점 계획 확인 필요.
- **[P2] typography 토큰 게이트 이미 RED** — raw fontSize 리터럴 16개 > cap 15 (pre-existing).
  16개 리터럴을 `--pq-text-*` 토큰으로 마이그레이션 필요(스타일 변경이라 신중).
- **[P2] inbox admin SoT 미통합** — `routes/inbox.py`가 `services/admin_emails.py` 미사용
  (현재 로직 동일해 무해하나 drift 리스크). 사소하지만 안전한 리팩터.

### pivox-brief

- **[P1] GHA 스케줄러 상태 미영속** — `data/brief_state.json`/`fng_history.json`이 gitignore +
  매 run fresh checkout이라 F&G 트렌드/"어제比"가 매번 합성, 알림 transition(수익률곡선 반전 등)이
  영구히 안 뜸 + 매일 "신규 극단"이 재발화. **수정방향**: actions/cache 또는 Supabase로 영속.
- **[P1] 미국 공휴일 날짜 시프트** — `engine/brief.py:79-111`. KST today를 미국 휴장 캘린더에
  직접 조회해 아침판에서 미국 휴장 배너 누락(추수감사절 등). **수정방향**: US 휴일은 `today-1`
  또는 US/Eastern 기준 조회.
- **[HIGH] 휴면 중복 launchd 스케줄러** — 재로드되면 아침 메일 2통 발송 위험. `launchctl unload` 권고.
- **[MEDIUM] 이메일 무재시도 + 실패 무알림**, **[MEDIUM] KIS 토큰 캐시 미영속**,
  **[LOW] Supabase RLS 무제한 insert**(id='default' 제약 권고), **[P2] /api/research maxDuration 없음**.

### dataready

- **[HIGH] `caseNormalize:"title"`이 약어 훼손** — USA→Usa, 그리고 value_variants도 미해결.
- **[MEDIUM] EUC-KR CSV mojibake로 조용히 파싱 + score 100/100** — 인코딩 감지 필요.
- **[MEDIUM] ragged row(초과 열) 값이 무보고로 유실** — `__parsed_extra` 이슈화 필요.
- **[LOW] verified_facts.json 오라클 stale-guard(해시) 부재.**
- **[P1] 업로드 크기 가드 부재** (index.html) — 대용량 파일 시 브라우저 freeze, Papa `worker:true` 미사용.
- **[P1] serve.mjs cleanUrls 로컬 미구현** → `/analysis` 로컬 404(prod는 정상). 로컬 QA 혼란.
- **[P2] analysis.html→KR 역링크 없음**, **[P3] revokeObjectURL 동기 호출 타이밍**.

---

## 오탐/문제없음으로 확인된 주요 항목 (재발 방지 기록)
- pivoxquant: CORS/rate-limit/CSRF/IDOR/캐시-스코핑/OAuth-state/KIS-AES-GCM/webhook-서명/dev-login
  전부 견고. 프론트 sw.js CACHE_VERSION·.env DEMO_MODE=0 diff는 정상. endpoints↔routes 122개 정합.
- pivox-brief: /api/research 입력검증 견고, service_role 키 노출 없음, kr_data→analysis-kr prod 404 = false alarm.
- dataready: 웹 XSS(esc 일관 적용), dup-row join, xlsx 멀티시트/수식/날짜 셀 모두 정상.
