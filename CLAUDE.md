# PivoxQuant — 세션 컨텍스트

> **이 파일의 규칙: 잰 것만 적는다. 재는 방법을 같이 적는다.** 모르면 "확인 불가"라고 적는다.
> 이 파일은 **매 세션 통째로 컨텍스트에 실린다** — 2026-09-11 에 33KB 를 줄였다. 여기엔 규칙과 한 줄 요약만 두고,
> 근거·이력·스냅숏은 `docs/claude/` 로 옮겼다 (섹션 이름과 함정 번호는 그대로라 코드 주석의 "CLAUDE.md §N" 참조가 유효하다).
> - 상태·측정값 스냅숏 `docs/claude/status.md` · 기술 스택·구조 상세 `docs/claude/stack.md`
> - 함정 전문 `docs/claude/traps.md` · 제품 전제 `docs/claude/product-premise.md` · 이력 `HANDOVER.md`
> 새 내용을 넣을 땐 **매 세션 필요한 규칙인지** 먼저 따져라. 사건 기록·수치 표는 docs 쪽에 쓰고 여기엔 한 줄 포인터만.

---

## 이 파일을 믿기 전에

수치는 **측정 시각과 함께** 적는다. 오래됐으면 다시 재라.

```bash
# 부팅 — URL rule / blueprint 수
RUN_SCHEDULER=0 POPULATE_CACHE_ON_BOOT=0 ./venv/bin/python -c "
from app import create_app
a=create_app(); print('rules', len(list(a.url_map.iter_rules())), '| bp', len(a.blueprints))"

# 백엔드 테스트
./venv/bin/python -m pytest -q | tail -2

# 프론트
cd frontend && npx vitest run && npx tsc --noEmit && npm run lint && npm run build
```

---

## 제품

**기록(記錄) 중심 개인 투자 회고 도구.** 유저가 이미 들고 있는 포트폴리오를 읽고,
사기 전에 멈춰 이유를 적게 하고, 그 기록을 나중에 거울처럼 되비춘다.
루프는 하나다 — **멈춤 → 기록 → 거울.** 미국 + 한국 주식. 1인 창업자(배상현). 클로즈드 베타, 무료.

### 핵심 3축 (측정 2026-09-01)

| 화면 | 하는 일 | 시세 필요? |
|---|---|---|
| `/pre-trade` **멈춤** | 사기 전 7문항 기록. 쿨다운은 현재 **0초** (`DEFAULT_COOLDOWN_SECONDS=0`, CEO가 제거) — 지금의 마찰은 시간이 아니라 질문 자체다 | ❌ |
| `/journal` **기록** | 기록 + behavior mirror 5종 (보유기간/회전율/집중도/물타기/손익처분) | ❌ |
| `/mirror` **거울** (홈) | 선언 페르소나 vs 관찰 페르소나(30일 9차원)의 **간극** + 드리프트 | ❌ |

**온보딩은 v3 5문항 + 법적 확인이다 (2026-09-06).** 보유기간 · 매매 빈도 · 종목 수 · −10% 대응 · 기록 습관.
답은 `investment_profiles.onboarding_answers_json` 에 **원문 그대로** 저장되고 `declared_vector_json` 으로 관찰 9축 눈금에 투영된다.
`/mirror` 의 "선언"은 이 벡터가 있으면 **유저 본인의 답**, 없으면 페르소나 센트로이드다 (`declared.source`).
유형 라벨·점수는 만들지 않는다. **V1(8문항)·V2(19문항)는 코드에서 삭제됐다** — 옛 payload 는 `ONBOARDING_UNKNOWN_QUESTIONNAIRE` 400.
설계: `docs/strategy/onboarding-questionnaire-v3_2026-09-06.md`.

**셋 다 시세를 한 번도 안 부른다** (`services/behavior/*.py` 는 시세 서비스를 import 하지 않는다 — 의도된 설계).
시세는 **오직 `/portfolio` 의 평가액** 때문에 존재하고, 평가액을 유저 본인 계좌에서 받으면 FMP 재배포 문제와 R7 이 함께 닫힌다.

### 나머지 화면
`/portfolio` (보유·NAV·거래내역) · `/settings` (이름·로그인·알림·데이터 내보내기/탈퇴) · `/support/contact` · `/support/inbox` — `/profile` 은 2026-09-12 해체(→ `/settings` 308)

---

## 지금 상태

2026-09-01 스냅숏(백엔드 호스팅 · 결제 게이트 · 측정값 표 · 당시 블로커)은 `docs/claude/status.md`. **날짜가 지났으니 다시 재고 믿어라.**
매 세션 필요한 사실만 여기 둔다:
- DB 는 Supabase Postgres. **접속은 session pooler 필수**(`aws-0-ap-northeast-2.pooler.supabase.com:5432`, 직결 호스트는 IPv4 로 안 풀린다). **DB 롤은 `pivox_app`** (postgres 아님).
- 결제는 prod 503 `BUSINESS_REGISTRATION_PENDING` 게이트로 꺼져 있다.
- `tests/test_scheduler_cron_jobs.py::EXPECTED_JOB_COUNT` 는 하드코딩 — cron job 을 더하거나 빼면 같이 고쳐라.
- 키를 찾기 전에 `.env` 부터 열어라 (`SHIP_BLOCKERS.md` B5 의 키 목록은 stale).

---

## 기술 스택

상세·근거는 `docs/claude/stack.md`.
- **Backend** Flask + SQLAlchemy + PostgreSQL(Supabase) / SQLite(local) · **Frontend** Next.js 16 + TS + Tailwind 4 + SWR + motion/react
- **AI 없음 — 코드까지 삭제됨** (2026-09-01). 되살릴 거면 소비자부터. 개인정보처리방침·가입 동의의 Anthropic 국외 이전 문구는 **2026-09-06 제거 완료**(§6-3 정정 이력에만 남음, `SHIP_BLOCKERS.md` R0 ✅ — 2026-09-21 grep 재확인). 남은 건 변호사 §28-8 확인뿐.
- **Broker** KIS read-only (`KIS_READ_ONLY` 가드). 토스 Open API 는 **운영자 본인 계좌 read-only 전용** — 리포트는 `services/behavior/*_mirror` 함수를 그대로 쓴다(두 벌 금지). 유저 브로커 연동은 `BROKER_LINKING_AVAILABLE=false`.
- **Data** FMP + KIS. ⚠️ **FMP 약관 §2.2.2 — Data Display Agreement 없이 유저 표시 금지(무료도 해당), 미체결.** 그래서 **벤더 시세의 유저 표시는 플래그 뒤에 있고 기본 꺼짐**(2026-09-19): 백엔드 `MARKET_DATA_DISPLAY_ENABLED`(`config.py`, `services/market_display.py`) + 프론트 `NEXT_PUBLIC_MARKET_DATA_DISPLAY`(`lib/market-display.ts`, 둘 다 켜져야 표시). 꺼지면 `/portfolio` 는 취득가 기준, `/api/market/*`·`/api/realtime/*` 는 503(환율·검색 예외), 52주 알림 잠김, NAV 스냅숏 기록도 멈춤. **무료·재배포 가능한 종가 소스는 국내·미국 모두 없다**(2026-09-19 약관 실측 — `docs/legal/R7_kis_market_data_options_2026-06-09.md` 상단 추기). 켜는 조건 = Agreement 체결.
- **Auth** Google + Kakao OAuth · **Payment** Stripe(게이트) · **Design** v3 락-인 (Vantablack + Bronze + Playfair + KR 컨벤션)

---

## 구조

트리·라우트 목록은 `docs/claude/stack.md`. 규칙만:
- `app.py` 의 `db.create_all()` 은 조건 없이 돈다. `models/` · `migrations/` 의 alembic 리비전은 **삭제 금지**.
- `routes/market.py` 는 4 라우트다 — 사라진 14개(FMP 다량 사용)를 되살리지 마라. **퀀트 코드·autotrade 는 없다.**
- `services/broker/` `mock_data/` `trading/` 은 추적 파일 0개인 빈 껍데기다.
- 프론트 `(dashboard)` = mirror · portfolio · pre-trade · journal · settings · support. `/home` → `/mirror`, `/profile` → `/settings` 308.
- ⚠️ **프론트가 쓰는 API 는 경로 문자열로 grep 하지 마라** — `endpoints.ts` 의 **심볼**(`API.market.fx`)로 소비자를 추적하라.

---

## ⚠️ 함정 — 한 줄 요약 (전문과 근거: `docs/claude/traps.md`, 번호 동일)

1. **빈 DB 를 alembic 으로 세우지 마라** — `flask db upgrade` 는 004 에서 죽는다. 앱을 1회 부팅(create_all) 후 반드시 `./venv/bin/python -m flask db stamp head`.
2. **`.env` 가 `override=True`** — 셸의 `RUN_SCHEDULER=0` 도 덮인다. prod 재현은 `.env` 를 잠시 치우고.
3. `.env.local` 의 `NEXT_PUBLIC_DEMO_MODE=1` 이면 백엔드가 아니라 fixture 를 본다.
4. **Template Hardcoding Guard 는 방어선 0개** — 그 green 은 증거가 아니다. 살아있는 legal 스위트:
   `./venv/bin/python -m pytest tests/test_disclaimer_sot.py tests/test_forbidden_terms_sync.py tests/test_legal_deep_scan_local.py tests/test_legal_filter.py tests/test_legal_filter_forbidden_parity.py tests/test_legal_scrub_decorator.py tests/test_pivoxaudit_secret_leak.py`
5. 로컬 grep 은 **ugrep**, 로컬 파이썬 3.12 · prod 3.11, Docker 없음 — prod 파이썬·이미지 빌드는 여기서 검증 못 한다.
6. pre-commit legal-guard 는 **추가된 줄만** 본다. 의도된 예외는 `// legal-ok` (`# noqa: legal` 은 ruff 가 오해).
7. **CAUS 는 삭제됐다 — 되살리지 마라.** 단 `users.is_simulated` 와 메일·푸시 가드는 **지우지 마라** (가상 유저 스윕이 아직 쓴다).
8. `services/access_guard.py` 는 **없다** — 테스트와 함께 `c1f61809`(2026-09-02)에서 삭제됐다. §101 화이트리스트 가드가 있다고 가정하지 마라.
9. `.dockerignore` 에서 `docs/` · `frontend/` · `tests/` · `scripts/` 를 빼지 마라 — 인프로세스 크론이 런타임에 읽는다(실패는 조용하다).
9-2. CSP `connect-src` 는 Render(`*.onrender.com`). `RAILWAY_BACKEND_URL` 이름은 render.yaml · next.config.ts · routes/auth.py · Vercel **네 곳을 한 번에**만 바꿔라.
10. **법적 스크럽 구현은 `services/legal_filter.scrub_response()` 하나** — 라우트 쪽 편의 헬퍼로 두 번째 복사본을 만들지 마라.
11. **메모리 디렉터리가 두 개**다: `~/.claude/projects/-Users-seanbae-Desktop---/`(장기, `legal_question_queue.md` · `DECISIONS.md`) 와 `…Desktop----pivoxquant/`(이 프로젝트). "없다" 전에 둘 다 봐라.
12. `endpoints.ts` 경로가 404 를 가리킬 수 있다 — 삭제 전 **심볼로 소비자를 세라**, 검증 스크립트는 `${id}` 보간을 먼저 치환.
13. `_do_migrations` 의 DDL 은 소비자(모델·라우트)부터 만들고, 소비자가 사라지면 DDL 도 지워라.
14. **베타 비번 리터럴을 어디에도 인용하지 마라** (커밋 제목에도 있다 — `git log --all -S` 로 직접 조회). pytest 가 이 한 건으로 빨가면 코드가 아니라 스윕 리포트 오염부터 의심하고 리터럴만 마스킹.

---

## 중요 원칙

- 🔴 **최신 정보 파악** — **코드/수치** = grep·Read 실측 (기억 인용 금지) /
  **시장·경쟁·규제** = WebSearch + 출처 날짜 확인 / **결정**(가격·법·수익모델) =
  메모리 `DECISIONS.md`.
- 🔴 **주장 범위 = 측정 범위.** 한 파일 재고 "전체가 그렇다"고 하지 마라.
  "~뿐이다 / 없다" 를 말할 프로브엔 `head` 를 걸지 마라. 결과를 말할 때 **무엇을
  쟀는지 같이** 적어라. (2026-09-01 에 이 규칙을 어겨 여러 번 틀렸다.)
- **API endpoint URL 변경 금지** — `frontend/src/lib/endpoints.ts` 와 1:1
- **routes/ · models/ · services/ 구조 유지**
- **시그널 라벨: POSITIVE / NEGATIVE / NEUTRAL** — BUY·SELL·HOLD 절대 금지 (자본시장법)
- **"AI Assistant"** — "AI Coach" · "투자 코치" 금지
- **추천·조언 언어 금지** — recommendation / advice / 추천 / 조언
- **DisclaimerBanner** — `(dashboard)/layout.tsx` 가 경로별 1회 마운트.
  페이지 안에서 중복 마운트 금지
- **없는 기능을 파는 카피 금지** — 삭제된 표면을 가리키는 링크·문구를 만들지 마라

### 법적 컴플라이언스
KIS 주문 disabled (read-only) · 한글+영문 면책 고지 · Cookie Consent ·
회원탈퇴(PIPA) · 가입 시 Terms checkbox 필수

---

## 알림

설정 → 알림은 **실제로 발신되는 것만** 노출한다. 발신자는 `app.py::_scheduled_price_alerts`(`price_52w` · `concentration`) + 월간 거울 리포트(`monthly_mirror`).
SoT = `models/user.py::NOTIFICATION_EVENT_IDS`, 노출 목록은 `visible_notification_event_ids()`. **`price_52w` 는 `MARKET_DATA_DISPLAY_ENABLED=0`(기본, 2026-09-19)이면 발신·노출 모두 꺼진다** — 벤더 시세라서. `concentration` 은 취득가 기준이라 계속 돈다. 옛 7종은 발신자가 없어 삭제 — 되살리려면 **발신자부터**.

---

## 개발

```bash
git config core.hooksPath .githooks        # clone 직후 1회
./venv/bin/python run.py                   # 백엔드 :5050
cd frontend && npm run dev                 # 프론트 :3000
```
canonical 트리 = `~/Desktop/취준/pivoxquant` (여기서 작업·커밋·푸시). `~/dev/pivoxquant` 는 2026-05-17 에 멈춘 버려진 사본.

**테스트 계정**: Google `seanbae1521@gmail.com` / KIS 계좌 read-only

---

## 출시 블로커

`SHIP_BLOCKERS.md` 가 SoT. 무료 베타에는 법적 블로커가 사실상 없다는 판단(2026-09-01, agent 판단이지 법률 자문 아님) —
변호사 의견서 질문 목록에 "무료 운영은 §101 밖인가"를 넣을 것.

---

## 제품 전제 — 불리한 근거를 먼저 본다

근거 전문은 `docs/claude/product-premise.md`. 결론만:
- "질문을 던진다" · "자동 수집" · "비-아첨" 은 해자가 아니다. **남은 진짜 자산은 "일어나지 않은 거래"** 다 (`services/pre_trade/friction_outcome.py`).
- 다음 세션이 답해야 할 질문은 코드가 아니다 — *"한국 개인투자자가 기록을 하긴 하는가."* 무료 베타의 목적은 이 답을 얻는 것.
