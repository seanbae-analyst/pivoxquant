# PivoxQuant — Session Handoff (2026-08-31 Updated)

> ⚠️ **2026-07-05 ~ 2026-08-30 약 7주간 프로젝트 중단.** 재개하며 실측 현행화.
> 이 파일은 매 턴 로드되므로 **틀린 값은 곧 잘못된 판단**이 된다. 상태 블록은
> 반드시 실측 후 갱신할 것. 상세 이력은 HANDOVER.md (v56~v66) 및
> `docs/archive/HANDOVER-history-v55-and-older.md` 참조.

## 프로젝트 개요
**기록(記錄) 중심 개인 투자 회고 도구.** 유저가 이미 들고 있는 포트폴리오를
읽고, 사기 전에 멈춰 이유를 적게 하고, 그 기록을 나중에 거울처럼 되비춘다.
루프는 하나다 — **멈춤 → 기록 → 거울**.
미국 + 한국 주식. 1인 창업자(배상현) 운영. 현재 클로즈드 베타.

> 2026-08-31 **대규모 prune 완료 (−123,000줄 / 레포 3.7G→1.2G).** 종목
> 스코어링 / 시그널 / 리스크보드 / AI 분석 / 디스커버 / 마켓 / 관심종목 /
> 그로스 / 컴패니언 / AI 트레이더 트윈 / 18종 아티팩트 리포트 — **전부
> 삭제됐다.** 이 파일에서 그 기능들을 찾지 마라. 없다.
> 코드가 필요하면 커밋 `80431ac0`·`1c23fac6`·`dfb4a98f` 이전 이력에 있다.
> 검증(2026-09-01 최종): pytest 2221 / vitest 353 / Playwright v2 smoke 16 /
> tsc·eslint clean / 부팅 135 rules / next build 36 routes. **prod 배포 완료.**

## 현재 상태 요약 (2026-09-01 실측)
🟡 **백엔드: DB 재구축 완료 / 앱 호스팅 대기** (2026-09-01 실측). Railway 계정이
  삭제되어 앱 + prod DB 가 함께 사라졌던 건에 대해, **DB 는 이미 새로 세웠다.**
  · **Supabase Postgres 가동 중** — 프로젝트 `pivoxquant` / `yjiztgummaxecriiuumt`
    / ap-northeast-2. 43 테이블 생성 + alembic `049` stamp 완료.
    앱 부팅 → `/api/health` **200 `{"db":"ok"}`** 실측됨.
    **로그인 이후 E2E 도 API 레벨은 통과** — dev-login → 생년월일 게이트 →
    `/api/mirror-home`·`/api/portfolio`·`/api/pre-trade/start`(행 INSERT)·
    behavior mirror 전부 200. 검증 데이터는 삭제해 DB 는 백지 상태다.
    접속은 **session pooler 경유 필수** (`aws-0-ap-northeast-2.pooler.supabase.com:5432`)
    — 직결 호스트 `db.*.supabase.co` 는 IPv4 로 해석되지 않는다.
    롤은 `postgres` 가 아니라 전용 `pivox_app` (Supabase 가 postgres 롤 비번 변경을 막는다).
  · 남은 것: **앱 호스팅** — Render 로 결정됨. `render.yaml` Blueprint 작성 완료,
    CEO 가입 + Blueprint 클릭 + 시크릿 붙여넣기만 남았다.
    붙여넣을 값: `.secrets/RENDER_PASTE_VALUES.txt` (gitignore, 커밋 안 됨).
  · 사라진 것: prod DB 데이터(클로즈드 베타라 실사용자 데이터는 사실상 없음),
    Railway env vars(BREVO_API_KEY 등 시크릿 **전부 재발급/재설정 필요**).
  · 로컬 `pivoxquant.db` 는 dev 사본이지 prod 백업이 아니다.
  → 런북: `docs/ops/backend-restore-2026-09-01.md`
✅ **프론트엔드: prod 라이브** — Vercel `www.pivoxquant.com` 200 정상, 실제 제품
  (로그인 게이트) 서빙 중. 마지막 배포 2026-06-29 (PR #531, demo mode OFF).
  Vercel 계정에 pivoxquant / pivox-brief / pivoxdata 3개 프로젝트 정상 존재.
**결제: Stripe 통합 완료, 게이트로 비활성** — `BUSINESS_REGISTRATION` 미완 +
  변호사 Q1-Q15 자문 대기로 prod 는 503 `BUSINESS_REGISTRATION_PENDING` 반환.
  사업자등록 459-01-03808 발급됨, 통신판매업 신고 + 유료결제 활성화는 의견서 후.
**코드**: 백엔드 복구는 `fix/backend-restore-render-supabase` → **PR #546**.
  ⚠️ 2026-09-01 정정: `38beb633` 을 "미푸시" 로 적어 뒀던 건 **틀렸다** —
  `origin/fix/email-provider-retry` 에 이미 올라가 있다. 미푸시가 아니라
  **미머지**다 (`git branch -a --contains 38beb633` 로 확인).

## 알려진 잔여 이슈 (2026-05-23 기준, 외부 액션 / 법무 의존)
- **이메일: 발신 ✅ / 수신 ✅**: **발신** = **Brevo HTTP API** (2026-06-30 전환 — Railway 가
  SMTP 아웃바운드를 막아 `OSError 101`, SendGrid 는 401. `BREVO_PROVIDER_PRIMARY=true` 로
  cascade SendGrid→Brevo→SMTP 의 우선순위를 뒤집어 사용. 코드: `services/email/brevo_provider.py`).
  ⚠️ 백엔드가 DOWN 인 현재는 발송 경로 전체가 미동작. **수신** =
  ImprovMX 포워딩 **active**. 근본원인은 alias 아니라 **옛 ImprovMX 계정 충돌**(도메인 "already
  registered") + **SPF에 improvmx 누락**이었음. 해결: ① DNS TXT 소유권 인증(`_improvmx` TXT)으로
  도메인을 seanbae1521 계정으로 이전 ② 가비아 SPF에 `include:spf.improvmx.com` 추가(sendgrid 유지).
  결과 MX✓·SPF✓·forwarding active, **ImprovMX 로그 "DELIVERED 250 OK gmail-smtp-in"** 확정.
  catch-all `*@pivoxquant.com → seanbae1521@gmail.com` (13개 alias 전부 커버). 최종 SPF =
  `v=spf1 include:spf.improvmx.com include:sendgrid.net ~all`. ⚠️ 자동발송 테스트메일(noreply@,
  동일도메인)은 Gmail 자체필터로 받은편지함 미표시 — 외부발신 실문의는 정상 도착. 가이드 `docs/ops/email-setup.md`.
- **Pro 아티팩트 이메일 동의 게이트**: `marketing_consent_at` NULL 유저는
  아티팩트 메일 미수신. 정통망법 §50 분리동의(변호사 Q-S1) 의존 — 코드는
  `PIVOX_CS1_CONSENT_ENABLED` 플래그 뒤 준비.
- **env 미설정 1건**: prod `missing_recommended:1` (SENDGRID_API_KEY 또는
  SENDGRID_WEBHOOK_PUBLIC_KEY — Railway Variables/Deploy Logs 에서 확인).
- 상세 버그 이력: `~/.claude/projects/-Users-seanbae-Desktop---/memory/qa_bug_log.md`

## 기술 스택
- **Backend**: Flask + SQLAlchemy + PostgreSQL — prod DB = **Supabase**
  (ap-northeast-2, session pooler 경유), 앱 호스팅 = **Render**(`render.yaml`,
  배포 대기) / SQLite (local)
- **Frontend**: Next.js 16 + TypeScript + Tailwind 4 + SWR + motion/react
- **AI**: Claude API — 남은 사용처는 지원 챗봇 / 이메일 문안 등 보조 경로.
  종목 SWOT·시그널·섹터·코칭 등 **분석 AI 는 표면과 함께 삭제됨**.
- **Broker**: KIS 한국투자증권 (read-only). Alpaca 는 2026-05-27 통합 제거,
  데이터 fallback stub 만 `ALPACA_ENABLED` 게이트(기본 OFF)로 잔존.
- **Data**: FMP Stable + KIS (공식 라이선스 데이터만). 2026-08-31 prune 으로
  FRED / pykrx / SEC EDGAR full service / DART insider 는 삭제. `services/data/edgar.py`
  만 잔존.
- **Auth**: Google + Kakao OAuth (email+password 없음).
- **Payment**: Stripe 통합 완료 (BUSINESS_REGISTRATION 게이트로 비활성)
- **Design**: v3 락-인 — Vantablack + Bronze + Playfair + KR 컨벤션.
  상세 메모리 `project_design_v3.md`.

## 백엔드 구조
> 2026-08-31 prune 후 실측. 등록 blueprint 25개 / URL rule **141개**
> (prune 전 249개). `create_app()` 부팅 검증됨.
```
pivoxquant/
├── app.py              # create_app() factory
├── config.py · extensions.py · security.py · run.py (port 5050)
├── models/             # SQLAlchemy 모델
├── migrations/         # Alembic (리비전 전량 보존 — 삭제 금지)
└── routes/             # 25 blueprint
    │  auth · portfolio · trades · pre_trade · behavior · mirror_home
    │  profile · settings계열(consents/email_preferences) · billing
    │  alerts · notifications · push · realtime · market(지수/FX만)
    │  support · inbox · feedback · health · data_status
    │  dev_auth · sim_onboard · command_center (opt-in)
    └── decorators.py
└── services/
    │  (services/quant/ 는 통째로 삭제됨 — 남겨뒀던 portfolio.py·risk_metrics.py
    │   조차 소비자가 0이었다. 퀀트 코드는 이 트리에 더 이상 없다.)
    ├── data/           # fetcher.py · fmp.py · kis_market_adapter.py ·
    │                   #   kr_fundamentals.py · edgar.py · realtime.py
    ├── behavior/       # 5종 mirror (holding/turnover/concentration/
    │                   #   averaging-down/profit-loss) — 거울 표면의 본체
    ├── pre_trade/ · profile/ · portfolio/ · trading/
    ├── ai/ · email/ · kis/ · broker/ · legal/ · scheduler/ · customer/
    ├── support/ · inbox/ · marketing/ · tax/ · mock_data/
    └── (루트) container(fetcher·ai·realtime 싱글턴) · cache_service ·
              serializers · fx_service · alert(벨 3종) · push 등
```

## 프론트엔드 구조
> 2026-09-01 실측. 대시보드 화면 **6개** (prune 전 19개).
> nav 파일에 있는 것 = 존재하는 페이지. hidden 목록은 더 이상 없다.
> `/home` 은 삭제됨 — `NEXT_PUBLIC_MIRROR_HOME` 플래그 뒤에서 거울과 같은
> 화면을 렌더하던 중복 문이었다. 이제 `/mirror` 가 유일한 홈이고, 로그인·온보딩
> 완료 후 착지 지점도 `/mirror` 다. `/home` 은 308 로 `/mirror` 에 리다이렉트.
```
frontend/src/
├── app/
│   ├── page.tsx                 # 랜딩(미로그인) / 홈 리다이렉트(로그인)
│   ├── landing/                 # 랜딩 본체 (features/* 마케팅 12페이지는 삭제)
│   ├── (auth)/                  # login · signup · oauth-finalize · onboarding(+broker)
│   ├── (dashboard)/
│   │   ├── mirror        # 거울 — 선언 vs 기록. PRIMARY
│   │   ├── portfolio     # 보유 종목 · NAV · 섹터 · 거래내역. PRIMARY
│   │   ├── pre-trade     # 멈춤 — 7문항 사전 기록. PRIMARY
│   │   ├── journal       # 결정 저널
│   │   ├── profile       # 페르소나 · 펄스 · 데이터 내보내기/삭제
│   │   ├── settings(+/profile)
│   │   └── support/      # 문의 · 챗봇 · inbox
│   ├── admin/ · beta/ · beta-gate/ · docs/ · feedback/nps/
│   ├── pricing · terms · privacy · contact · support · delete-cancel
│   └── card/[token]      # 폐기된 공유링크 tombstone (404 대신 안내)
├── components/
│   ├── layout/           # terminal-sidebar · bottom-nav · top-bar · dashboard-layout
│   ├── mirror/ · portfolio/ · journal/ · pre-trade/ · profile/
│   ├── dashboard/        # living-cfo-status(2 layer) · weekly-pulse · persona-*
│   ├── landing/ · settings/ · support/ · broker/ · account/ · feedback/
│   ├── terminal/top-ticker · shared/ · share/ · ui/ · pwa/ · auth/
├── lib/
│   ├── auth.ts · endpoints.ts · hooks.ts · types.ts · format.ts
│   ├── cfo/hooks.ts · pre-trade.ts · realtime.tsx · locale.tsx · demo.ts
│   └── use-keyboard-nav.tsx (G+P 포트폴리오 / G+M 거울 / G+J 저널)
```

## 로컬 git hooks (2026-05-19 신규)

GitHub Actions billing 결제 차단으로 로컬 hooks 이전. clone 직후 1회 실행:

```bash
git config core.hooksPath .githooks
```

상세: `docs/dev/local-hooks.md`

## 서버 기동
```bash
# 🟥 경로 정정 (2026-05-22 v49): canonical 트리 = ~/Desktop/취준/pivoxquant.
#   - 이 트리의 HEAD = origin/main = prod 배포 커밋 (실측 0/0 동기화).
#   - 2026-05-17 의 ~/projects/pivoxquant relocation 은 v44.6(2d0699bf, 5/17)에
#     멈춘 버려진 사본 — CEO 가 그 후 Desktop 으로 복귀해 작업/배포 중.
#   - 따라서 아래 "Desktop 사용금지" 옛 안내는 STALE. Desktop 에서 작업/커밋/푸시.
#   - iCloud .git 손상은 과거 이슈 — 재발 시 git fsck 후 대응(상시 손상 아님).

# 백엔드 (port 5050)
cd ~/Desktop/취준/pivoxquant && ./venv/bin/python run.py

# 프론트엔드 (port 3000)
cd ~/Desktop/취준/pivoxquant/frontend && npm run dev
```

## 테스트 계정
- Google: seanbae1521@gmail.com (OAuth redirect URI 등록 완료 + commit `d153340` 이후 동작)
- KIS: 계좌번호 XXXXXXXX-01 (read-only)
- Alpaca: paper trading 계정 (.env에 키 있음)

## 알림 (2026-09-01 개편)
설정 → 알림 매트릭스는 **실제로 발신되는 2종만** 노출한다:
`price_52w`(52주 고/저 스윕) · `concentration`(섹터 30% 초과 스윕). 둘 다
app.py 의 `_scheduled_price_alerts` 크론이 발신하고, `_BELL_KIND_TO_EVENT_ID`
를 통해 토글이 실제로 걸린다. SoT = `models/user.py::NOTIFICATION_EVENT_IDS`
(프론트 `notifications-matrix.tsx` 와 1:1). 옛 7종(weekly_memo /
earnings_pre_brief / signal_state / risk_breach / pulse_prompt / brag_card /
broker_sync_error)은 전부 발신자가 없어 삭제 — 되살리려면 **발신자부터** 만들 것.

## 중요 원칙
- 🔴 **최신 정보 파악 (모든 agent 필수)** — CEO 반복 지시 (2026-05-30 "자꾸 옛날 데이터 가져온다"). **코드/수치** = grep·Read 실측 (메모리·기억 인용 금지) / **시장·경쟁·규제** = WebSearch + 출처 날짜 확인 (훈련데이터 금지, 예: 키움 자동일지 = 검색으로 확인) / **결정**(가격·법·수익모델) = `~/.claude/projects/-Users-seanbae-Desktop---/memory/DECISIONS.md` (SoT) / **동적수치**(HEAD·cron·test) = SessionStart hook LIVE 값. 오늘 날짜 기준. 모르면 "확인 불가". "최근/요즘" 막연 표현 금지 → 출처+날짜.
- **퀀트 코드 없음** — `services/quant/` 는 2026-08-31 통째로 삭제됐다.
  engine / risk_defense / models / backtester / portfolio / risk_metrics 전부.
  없는 파일을 찾거나 되살리지 마라. 다시 필요해지면 커밋 `1c23fac6` 이전
  이력에서 꺼내되, 그때는 "왜 이 제품에 알파 스코어링이 필요한가"부터 답할 것.
  autotrade 는 2026-04-27 비활성화 → 2026-05-05 물리 삭제 (투자일임업 회피,
  rollback 은 git tag `legal-pre-autotrader-removal` 만)
- **routes/, models/, services/ 구조 유지**
- **API endpoints URL 변경 금지** — `endpoints.ts`와 1:1 매핑
- **시그널 라벨: POSITIVE/NEGATIVE/NEUTRAL** — BUY/SELL/HOLD 절대 사용 금지 (자본시장법)
- **"AI Assistant"** — "AI Coach", "투자 코치" 사용 금지 (법적)
- **추천/조언 언어 금지** — "recommendation", "advice", "추천", "조언" 사용 금지
- **DisclaimerBanner** — 모든 데이터 표시 페이지에 면책 배너 필수.
  `(dashboard)/layout.tsx` 가 경로별로 1회 마운트한다 (mirror/journal/pre-trade =
  "coaching", 나머지 = "signal"). 페이지 안에서 중복 마운트 금지.
- **없는 기능을 파는 카피 금지** — 2026-08-31 prune 으로 랜딩 메가메뉴 3개 그룹과
  Companion 업셀(가짜 좌석 카운트 포함)을 지운 이유다. 삭제된 표면을 가리키는
  링크·문구를 새로 만들지 마라.

## 법적 컴플라이언스
- KIS 주문 기능 disabled (read-only)
- 모든 분석 페이지에 한글+영문 면책 고지
- Cookie Consent 구현됨
- 회원탈퇴 기능 (PIPA 준수)
- Terms checkbox 필수 (회원가입 시)

### Template Hardcoding Guard

**방어선 2개 (이중 방어)**

| 방어선 | 위치 | 실행 환경 | 검증 대상 |
|--------|------|-----------|-----------|
| CI legal-guard | `.github/workflows/legal-guard.yml` | ubuntu-latest (GNU grep) | PR + push to main 자동 실행 |
| 로컬 pytest | `tests/test_no_hardcoded_samples.py` | 크로스 플랫폼 (Python) | 로컬 개발 + CI 동일 실행 |

**macOS 주의사항**

`.github/workflows/legal-guard.yml` 의 `grep -rnPzo` 는 PCRE (`-P`) 플래그를 사용한다.
macOS 기본 BSD grep 은 `-P` 를 지원하지 않으며, 오류 메시지(`grep: invalid option -- P`)와 함께 exit 0 을 반환한다 — 즉, 위반이 있어도 **통과로 오탐**한다.

로컬(macOS) 에서 template 변경 후 반드시 pytest 로 검증:
```bash
pytest tests/test_no_hardcoded_samples.py -v
```

**선택: GNU grep 로컬 설치**
```bash
brew install grep
# 설치 후 ~/.zshrc 또는 ~/.bash_profile 에 추가:
# export PATH="$(brew --prefix)/opt/grep/libexec/gnubin:$PATH"
```
설치 후에는 `grep -Pzo` 가 macOS 에서도 정상 동작한다.

**PR 머지 전**

CI legal-guard job (`Legal Guard / No hardcoded sample tickers or money in template defaults`) 이 green 이어야 머지 가능. CI 는 ubuntu-latest (GNU grep) 에서 실행되므로 `-Pzo` 가 정상 작동한다.

## 출시까지 남은 것 (2026-08-31 갱신)

### 🔴 최우선 — 백엔드 복구 (1·2 완료 / 3~5 남음)
prod 프론트는 살아있지만 **로그인 이후가 전부 죽어 있다**. 순서대로:

1. ✅ **호스팅 선정** — **Render(앱) + Supabase(Postgres)**. 2026-09-01 결정.
2. ✅ **DB 재생성 완료** — Supabase `pivoxquant` (ap-northeast-2), 43 테이블 +
   alembic `049` stamp + `/api/health` 200 실측.
   ⚠️ **인수인계서가 틀렸던 지점**: "alembic 52 리비전으로 스키마 100% 재현"은
   **사실이 아니다.** `app.py:414` 의 `db.create_all()` 이 조건 없이 돌기 때문에,
   `flask db upgrade` 는 자기가 실행되기 전에 create_all 이 만들어 놓은 테이블과
   충돌해 **004 에서 DuplicateTable 로 죽는다**(실측). 스키마의 SoT 는 **ORM 모델**
   이고 alembic 은 이력일 뿐이다 — `app.py:1024` 주석이 이미 "prod 는 alembic
   미실행" 이라고 적고 있다. 빈 DB 를 세우는 올바른 순서는
   **① 앱 1회 부팅(create_all) → ② `flask db stamp head`** 이다. ②를 빼먹으면
   `alembic_version` 이 없어 다음 마이그레이션이 001 부터 다시 돌다 영구히 깨진다.
3. **시크릿 재설정** — Railway env vars 전량 소실.
   `render.yaml` 이 `sync: false` 로 Render 에게 물어보게 해 뒀고, 붙여넣을 값과
   출처는 `.secrets/RENDER_PASTE_VALUES.txt` 에 있다(gitignore).
   `DATABASE_URL` 과 `PIVOX_BROKER_ENCRYPTION_KEY` 는 이미 생성해 넣어 뒀다.
   `DEV_LOGIN_SECRET` 은 **절대 금지** — `routes/__init__.py` 가 플랫폼 마커
   (Railway/**Render**/Fly) 또는 `FLASK_ENV=production` 감지 시 부팅을 거부한다.
4. **프론트 재연결** — Vercel 의 `RAILWAY_BACKEND_URL`(또는 `NEXT_PUBLIC_API_URL`)
   을 Render URL 로. `vercel env` + `vercel redeploy`. vercel CLI 는 인증돼 있다.
   ⚠️ 이 값이 `/api` 프록시의 SoT다 (next.config.ts:9-10).
5. **검증** — `/api/health` 200 → 로그인 → `/mirror` 렌더 → `/portfolio` 포지션.
   Google/Kakao OAuth 콘솔의 **redirect URI 에 Render 도메인 추가**가 선행돼야 한다.

**Dockerfile 은 2026-09-01 에 122→63 줄로 줄였다** (삭제된 PDF/PNG 렌더용
폰트스택·Chromium 제거). 다만 **이 머신에 Docker 가 없어 정적 감사만 했다** —
새 호스트의 첫 빌드가 실질 검증이다. 실패하면 `git show c982e273^:Dockerfile`
로 옛 버전 대조.

- ✅ **prod 프론트 재배포 완료** (2026-09-01, PR #538·540·541·542·543·544).
  화면 6개, 삭제 경로 18개는 살아있는 목적지로 308 리다이렉트, sitemap 7 URL.

### 🔴 출시 BLOCKER (외부 / 법무 의존 — CEO 액션)
- **변호사 의견서 Q1-Q15 + Q-S1** — 유료결제 활성화 BLOCKER. `legal_question_queue.md`.
- **통신판매업 신고** — 사업자등록(459-01-03808)은 발급됨, 통신판매업 별도.
- **이메일 수신(MX)** — `docs/ops/email-setup.md` (가비아 콘솔 ImprovMX).
- **SENDGRID_API_KEY 확인** — Railway Variables (발신 실제 작동 확정).

### 🟠 코드 측 (내부 — 자율 진행 가능)
- ✅ 이메일 동의 silent-drop 비-silent화 (`fcbd1f55`). signup 동의 캡처(part-2)는
  routes/auth.py **frozen** + Q-S1 의존.
- prune 후속: 삭제된 표면을 참조하던 문서·메모리 정리 (일부 잔존 가능).
- 잔여 deferred (owner 판단): 부분환불 §17 / 국외이전 §28-8.
  billing/lawyer 의존이라 자율 빌드 제한적.
- ⬛ 삭제된 항목: artifact 18종 §50 카테고리 / DCA XIRR / lookahead /
  Composer synthetic / KR 52w — 해당 기능 자체가 없어졌으므로 백로그에서 제외.

## 유저 플로우 자동 테스트 방안
Claude in Chrome MCP + user-tester agent 로 자동 테스트 가능 (Chrome 연결 필요 — CEO 세션).
prune 후 플로우는 3개로 줄었다: 가입→온보딩→첫 포지션 / 사전기록(pre-trade) /
거울 열람.
상세: `~/.claude/projects/-Users-seanbae-Desktop---/memory/qa_bug_log.md` 하단 참조.

## 메모리 파일 위치
모든 프로젝트 지식은 `~/.claude/projects/-Users-seanbae-Desktop---/memory/` 에 저장:
- `qa_bug_log.md` — 버그 17개 + 출시 전 작업 23개 + 유저플로우 테스트 방안
- `product_features.md` — 기능 맵
- `design_system.md` — 디자인 가이드
- `project_tech_decisions.md` — 기술 결정사항
- `security_checklist.md` — 보안 체크리스트
- `legal_compliance.md` — 법적 컴플라이언스
- 기타 20+ 메모리 파일 (MEMORY.md에서 인덱스 확인)
