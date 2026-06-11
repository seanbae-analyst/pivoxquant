# PivoxQuant — Session Handoff (2026-05-23 Updated)

> ⚠️ 이 파일은 2026-04-14 작성 후 오래 STALE 상태였다 (백엔드 85% / 미배포 /
> 결제 미연결 등). 2026-05-23 에 실측 기준으로 현행화. 옛 "당장 고쳐야 할
> CRITICAL/HIGH 버그 목록" (Add Position 불가, Search 안 됨 등) 은 **전부 해결**
> 되어 삭제했다. 상세 진행 이력은 메모리 MEMORY.md 의 세션 로그 참조.

## 프로젝트 개요
AI + Quant 기반 개인 투자 어드바이저 플랫폼.
미국 + 한국 주식 지원. SaaS 3티어 (Free / Pro ₩9,900 / Premium ₩19,900).
1인 창업자(배상현) 운영. **현재 클로즈드 베타 + 출시 직전.**

## 현재 상태 요약 (2026-05-23 실측)
**백엔드: prod 라이브** — Railway `web-production-7b484b.up.railway.app`, PostgreSQL,
  200+ 엔드포인트, pytest 3000+ 통과. health version = git sha.
**프론트엔드: prod 라이브** — Vercel `pivoxquant.com` (베타 게이트 307), Next.js 16,
  vitest 450+ 통과. V2 디자인 플래그 9개 모두 prod true.
**인프라: 배포 완료** — Railway(BE, GitHub auto-deploy 정상화 v46) + Vercel(FE).
  배포 메커니즘 상세는 메모리 MEMORY.md DevOps 섹션 참조.
**결제: Stripe 통합 완료, 게이트로 비활성** — 코드 완성. `BUSINESS_REGISTRATION`
  미완 + 변호사 Q1-Q15 자문 대기로 prod 는 503 `BUSINESS_REGISTRATION_PENDING`
  반환. 사업자등록 459-01-03808 발급됨, 통신판매업 신고 + 유료결제 활성화는
  변호사 의견서 후.

## 알려진 잔여 이슈 (2026-05-23 기준, 외부 액션 / 법무 의존)
- **이메일: 발신 ✅ / 수신 ✅ (2026-06-04 해결)**: **발신** = SendGrid(SPF/DKIM/DMARC). **수신** =
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
- **Backend**: Flask + SQLAlchemy + **PostgreSQL (Railway, prod)** / SQLite (local test)
- **Frontend**: Next.js 16 + TypeScript + Tailwind 4 + SWR + motion/react
- **AI**: Claude API (Anthropic) — SWOT, Chat, Sector, Coaching, Earnings Tone, Artifacts
- **Broker**: KIS 한국투자증권 (read-only). ~~Alpaca~~ 2026-05-27 통합 제거 (commit 6bea95f8, c3801359) — 데이터 fallback stub `services/data/alpaca_market_adapter.py` 만 `ALPACA_ENABLED` 게이트(기본 OFF)로 비활성 보존, 완전제거는 별도 task.
- **Data**: FMP Stable + KIS + SEC EDGAR (공식 라이선스 데이터만). Alpaca 데이터경로는 비활성(위 참조).
- **Auth**: Google + Kakao OAuth (email+password 없음). 라이브 동작 정상.
- **Payment**: Stripe 통합 완료 (BUSINESS_REGISTRATION 게이트로 비활성)
- **Design**: v3 락-인 — Vantablack + Bronze + Playfair + KR 컨벤션 (옛 Nexora
  purple/blue gradient 는 폐기). 상세 메모리 `project_design_v3.md`.

## 백엔드 구조
> ⚠️ 2026-05-24 현행화. 옛 트리는 engine.py / quant_models.py / risk_defense.py /
> data_fetcher.py / fmp_service.py / ai_service.py 등을 루트에 표기했으나, 전부
> `services/` 하위 패키지로 재편되었다(루트에 해당 .py 없음). 실측 반영:
```
pivoxquant/               # 2026-05-17 wave 13: 'stockpilot/' 명칭은 폐기
├── app.py              # create_app() factory
├── config.py           # Config 클래스
├── extensions.py       # db, login_manager
├── run.py              # 진입점 (port 5050)
├── security.py         # CORS/RateLimit/CSRF/세션만료
├── models/             # SQLAlchemy 모델 (10개+)
├── routes/             # Flask Blueprint (40+ 파일, 200+ endpoints)
├── migrations/         # Alembic
└── services/           # 비즈니스 로직 (전부 여기로 통합)
    ├── quant/          # engine.py(4-pillar) · models.py(퀀트모델) · risk_defense.py
    │                   #   (7-Layer) · risk_metrics.py(GKYZ/LedoitWolf/Sortino) ·
    │                   #   portfolio.py(HRP/ERC/MaxDiv) · signals.py · backtester.py ·
    │                   #   canslim.py · indicators.py · composer.py · model_catalog.py
    ├── data/           # fetcher.py(가격) · fmp.py(FMP stable+budget) ·
    │                   #   kis_market_adapter.py · kr_fundamentals.py · edgar.py ·
    │                   #   sec_edgar_service.py · dart_* · fred_service.py · realtime.py
    │                   #   (pykrx_service.py 는 ToS 위반으로 비활성 stub)
    ├── ai/             # Claude API (SWOT/Chat/Sector/Coaching/EarningsTone/Artifacts)
    ├── kis/            # KIS read-only (주문 disabled) + token_manager(AES-GCM)
    ├── broker/         # user_kis_service.py (KIS read-only). Alpaca 통합 제거됨(2026-05-27)
    ├── artifacts/      # 18 artifact type (PDF/PNG/HTML — User as CFO). SoT=routes/artifacts.py
    │                   #   _ARTIFACT_DISPATCH (생성 15 + interactive 3). 템플릿 18개와 일치.
    │                   #   tier: Pro 9 / Premium 6 / 무료·universal 3 + living_mirror — 2026-06-11
    │                   #   B2 가격표 정렬(SoT=pricing/page.tsx, lock=test_artifact_tier_alignment.py)
    ├── legal/          # legal_filter scrub · §101 detector · forbidden_terms
    ├── email/          # EmailSender + sendgrid/brevo provider cascade
    ├── profile/        # questionnaire(20문항) · investor profiles
    ├── behavior/ · pre_trade/ · trading/ · twin/ · scheduler/ · customer/ · agents/
    └── (루트 모듈) container · serializers · fx_service · cache_service ·
                      alert · alert_service · error_responses · push 등
```

## 프론트엔드 구조
```
frontend/src/
├── app/
│   ├── page.tsx                    # 랜딩 (미로그인) / 홈 리다이렉트 (로그인)
│   ├── globals.css                 # Nexora 디자인 시스템 (--sp-* 변수)
│   ├── (auth)/login, signup, onboarding  # 인증 플로우
│   ├── (dashboard)/               # 메인 대시보드 (13개 페이지)
│   │   ├── home, market, signals, discover, watchlist
│   │   ├── detail/[ticker], alerts, ai-chat, ai
│   │   ├── settings, risk  (autotrade REMOVED 2026-04-27 per legal)
│   ├── pricing/                    # 3-tier 가격표
│   ├── features/                   # 6개 기능 소개 페이지
│   ├── terms/, privacy/            # 법적 문서
├── components/
│   ├── landing/landing-page.tsx    # 10-section 랜딩
│   ├── dashboard/                  # positions-list, equity-chart, signals-widget 등
│   ├── layout/                     # sidebar, top-bar, bottom-nav, dashboard-layout
│   ├── ui/                         # tier-gate, disclaimer-banner, loading-skeleton 등
│   ├── pwa/                        # install-prompt, push-permission
├── lib/
│   ├── auth.ts                     # useAuth hook
│   ├── endpoints.ts                # 백엔드 API URL 매핑
│   ├── hooks.ts                    # SWR data hooks (일부 미사용)
│   ├── types.ts                    # TypeScript 인터페이스
│   ├── format.ts                   # 숫자/날짜 포매터
│   ├── realtime.tsx                # SSE EventSource provider
│   ├── push.ts                     # Web Push (미사용)
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

## 중요 원칙
- 🔴 **최신 정보 파악 (모든 agent 필수)** — CEO 반복 지시 (2026-05-30 "자꾸 옛날 데이터 가져온다"). **코드/수치** = grep·Read 실측 (메모리·기억 인용 금지) / **시장·경쟁·규제** = WebSearch + 출처 날짜 확인 (훈련데이터 금지, 예: 키움 자동일지 = 검색으로 확인) / **결정**(가격·법·수익모델) = `~/.claude/projects/-Users-seanbae-Desktop---/memory/DECISIONS.md` (SoT) / **동적수치**(HEAD·cron·test) = SessionStart hook LIVE 값. 오늘 날짜 기준. 모르면 "확인 불가". "최근/요즘" 막연 표현 금지 → 출처+날짜.
- **핵심 퀀트 엔진 신중 수정** — `services/quant/`(engine/risk_defense/risk_metrics/
  portfolio/backtester 등)는 검증된 완성 코드. 버그 fix 시 수식 단위/회귀 테스트 필수.
  autotrade 기능은 2026-04-27 비활성화 → 2026-05-05 물리 삭제 (투자일임업 회피, rollback 은 git tag `legal-pre-autotrader-removal` 만)
- **routes/, models/, services/ 구조 유지**
- **API endpoints URL 변경 금지** — `endpoints.ts`와 1:1 매핑
- **시그널 라벨: POSITIVE/NEGATIVE/NEUTRAL** — BUY/SELL/HOLD 절대 사용 금지 (자본시장법)
- **"AI Assistant"** — "AI Coach", "투자 코치" 사용 금지 (법적)
- **추천/조언 언어 금지** — "recommendation", "advice", "추천", "조언" 사용 금지
- **DisclaimerBanner** — 모든 분석/시그널 페이지에 면책 배너 필수

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

## 출시까지 남은 것 (2026-05-23 기준)

옛 P0/P1 기능 미동작 목록(Portfolio/Search/Watchlist/Risk/Discover/알림벨/
프로필/Alpaca/코스피·코스닥/OAuth)은 **전부 구현·배포 완료**. 남은 것은:

### 🔴 출시 BLOCKER (외부 / 법무 의존 — CEO 액션)
- **변호사 의견서 Q1-Q15 + Q-S1** — 유료결제 활성화 BLOCKER. `legal_question_queue.md`.
- **통신판매업 신고** — 사업자등록(459-01-03808)은 발급됨, 통신판매업 별도.
- **이메일 수신(MX)** — `docs/ops/email-setup.md` (가비아 콘솔 ImprovMX).
- **SENDGRID_API_KEY 확인** — Railway Variables (발신 실제 작동 확정).

### 🟠 코드 측 (내부 — 자율 진행 가능)
> 2026-06-01 실측 갱신: 아래 다수가 이미 처리/빌드 확인됨 (메모리 STALE 정정).
- ✅ 이메일 동의 silent-drop 비-silent화 (sender.py debug→info, `fcbd1f55`). signup 동의 캡처(part-2)는 routes/auth.py **frozen** + Q-S1 의존.
- ✅ flaky 테스트 — test_daytrade_smoke/test_fx_staleness **이미 격리 fix됨, 전체 스위트 green** (2026-06-01 exit0). 옛 "full suite fail"은 STALE.
- ✅ artifact 18 send() §50 카테고리 prep (INFORMATION, `a82fcb89`, flag-off inert).
- 잔여 deferred (owner 판단): 부분환불 §17 / 국외이전 §28-8 / DCA XIRR / lookahead / Composer synthetic / KR 52w. 대부분 billing/lawyer/frozen 의존이라 자율 빌드 제한적.

## 유저 플로우 자동 테스트 방안
Claude in Chrome MCP + user-tester agent 로 6개 플로우 자동 테스트 가능 (Chrome 연결 필요 — CEO 세션).
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
