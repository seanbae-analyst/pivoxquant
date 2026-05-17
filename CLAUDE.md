# PivoxQuant — Session Handoff (2026-04-14 Updated)

## 프로젝트 개요
AI + Quant 기반 개인 투자 어드바이저 플랫폼.
미국 + 한국 주식 지원. 실제 출시 목표 (SaaS 3티어: Free/Pro ₩9,900/Premium ₩19,900).
1인 창업자(배상현) 운영. 취준 겸 사이드프로젝트.

## 현재 상태 요약 ⚠️
**백엔드: 85% 완성** — 퀀트 엔진, 58개 모델, 85+ API 엔드포인트, 보안 미들웨어 완료
**프론트엔드: 50% 완성** — 27개 페이지 존재하나 핵심 기능 다수 미동작 (아래 버그 목록 참조)
**인프라: 미배포** — 로컬 개발만 완료, Vercel/Railway 배포 안 됨
**결제: 미연결** — Stripe 코드 있으나 API Key/Product ID 미매핑

## 🚨 CEO 직접 테스트 결과 — 당장 고쳐야 할 것들

### CRITICAL (서비스 자체가 안 됨)
1. **Add Position 불가** — `/portfolio` 페이지 없음(404). 매수/매도 모달도 없음. → 페이지 + 모달 신규 생성 필요
2. **Search Stock 안 눌림** — 상단 검색바 클릭/입력 불가
3. **Watchlist 추가 불가** — 종목 추가 UI 동작 안 함
4. **Risk 페이지 안 뜸** — 빈 페이지, 7-Layer Risk Defense 프론트 미연동
5. **Discover 데이터 안 나옴** — FMP 402 에러 연관 가능

### HIGH (핵심 UX 깨짐)
6. **알림 벨 안 눌림** — 우측 상단 아이콘 클릭 불가
7. **프로필 아이콘 안 눌림** — 드롭다운 메뉴 없음
8. **Connect Alpaca 안 눌림** — Settings 연결 버튼 동작 안 함
9. **코스피/코스닥 없음** — Market 페이지에 한국 시장 데이터 없음
10. **Contact 이메일 가짜** — 4곳에 각각 다른 가짜 도메인 (.app/.io/.me)
11. ~~**Google/Kakao OAuth 미설정**~~ — **RESOLVED 2026-04-19** (commit `d153340` stateless HMAC state) + 콘솔 redirect URI 등록 완료 (CEO 2026-05-08 confirm). 라이브 동작 정상.

### 상세 버그 목록: `~/.claude/projects/-Users-seanbae-Desktop---/memory/qa_bug_log.md` 참조

## 기술 스택
- **Backend**: Flask + SQLAlchemy + SQLite (→ PostgreSQL 전환 예정)
- **Frontend**: Next.js 16 + TypeScript + Tailwind 4 + SWR + motion/react
- **AI**: Claude API (Anthropic) — SWOT, Chat, Sector, Coaching
- **Broker**: Alpaca (US, paper=True) + KIS 한국투자증권 (read-only)
- **Data**: FMP v4 Stable ($29 Premium — 750 req/min, soft daily cap 10k) + Alpaca + SEC EDGAR
- **Auth**: Google + Kakao OAuth (email+password 없음)
- **Payment**: Stripe (코드만 있음, 미연결)
- **Design**: Nexora template 기반 — purple/blue/pink gradient, clean white

## 백엔드 구조
```
pivoxquant/               # 2026-05-17 wave 13: 'stockpilot/' 명칭은 폐기
├── app.py              # create_app() factory
├── config.py           # Config 클래스
├── extensions.py       # db, login_manager
├── run.py              # 진입점 (port 5050)
├── security.py         # CORS/RateLimit/CSRF/세션만료
├── models/             # SQLAlchemy 모델 (10개+)
├── routes/             # Flask Blueprint (40+ 파일, 200+ endpoints)
├── services/           # 비즈니스 로직 (container, serializers, fx, cache, alert, push, error_responses)
├── engine.py           # QuantEngine (1146줄) — 4-pillar scoring
├── quant_models.py     # 58 퀀트 모델 (StatArb, MeanReversion, TSMOM, ML 등)
├── risk_defense.py     # 7-Layer Risk Defense (VaR, Correlation, VIX, Tail, Daily, Sector, Cash)
├── risk_models.py      # GKYZ, LedoitWolf, ComponentES, ConditionalDD, TailRatio, Sortino
├── portfolio_models.py # HRP, TailRiskParity, MaxDiv, ERC, MinVariance
├── signal_models.py    # DispositionEffect, Herding, SentimentDivergence, OrderFlow, Anchoring
├── ai_models.py        # EarningsCallTone, SectorRotation, RiskSummary
├── backtester.py       # 백테스트 (transaction costs, Sharpe/Sortino/Calmar)
├── data_fetcher.py     # Alpaca→FMP 폴백, KIS KR데이터
├── fmp_service.py      # FMP v4 stable API, TTL cache, budget enforcement
├── kis_service.py      # KIS read-only (주문 disabled)
├── ai_service.py       # Claude API
├── realtime_service.py # SSE 실시간 가격
├── investor_profiles.py # 8 투자자 유형
├── questionnaire.py    # 20문항 온보딩
├── canslim.py          # CAN SLIM 7-factor screener
├── indicators.py       # 10 tech + 8 fundamental indicators
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

## 서버 기동
```bash
# 2026-05-17 wave 13: 경로 갱신. iCloud Desktop sync 가 ~/Desktop/취준/ 의
# .git 을 무한히 손상시켜 PR #376 에서 ~/projects/pivoxquant 로 relocation
# 완료. Desktop 사본은 사용 금지.

# 백엔드 (port 5050)
cd ~/projects/pivoxquant && ./venv/bin/python run.py

# 프론트엔드 (port 3000)
cd ~/projects/pivoxquant/frontend && npm run dev
```

## 테스트 계정
- Google: seanbae1521@gmail.com (OAuth redirect URI 등록 완료 + commit `d153340` 이후 동작)
- KIS: 계좌번호 XXXXXXXX-01 (read-only)
- Alpaca: paper trading 계정 (.env에 키 있음)

## 중요 원칙
- **기존 백엔드 서비스 파일 수정 금지** — engine.py, quant_models.py, risk_defense.py 등은 완성 상태. autotrade 기능은 2026-04-27 비활성화 → 2026-05-05 물리 삭제 (투자일임업 회피, rollback 은 git tag `legal-pre-autotrader-removal` 만)
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

## 다음 세션 TODO (우선순위 순)

### 🔴 P0 — CEO가 직접 해야 하는 것
1. ~~Google Cloud Console / Kakao Developers OAuth redirect URI~~ — **RESOLVED 2026-04-19 + 콘솔 등록 완료 2026-05-08**

### 🔴 P0 — 서비스 자체가 안 되는 것
3. Portfolio 페이지 + Add Position + 매수/매도/수정 모달 구현
4. Search Stock 검색바 동작
5. Watchlist 종목 추가 기능
6. Risk 페이지 데이터 표시 + Risk Defense 연동
7. Discover 종목 스캔 데이터 로딩

### 🟠 P1 — 핵심 UX
8. 알림 벨 드롭다운
9. 프로필 드롭다운 메뉴
10. Connect Alpaca 버튼 동작
11. 코스피/코스닥 지수 Market 페이지에 추가
12. 로그인→온보딩→홈 전체 플로우 검증

### 🟡 P2 — 런칭 전 필수
13. Stripe 결제 연결 (API Key + Product ID + test mode 검증)
14. Contact 이메일 도메인 통일 + 메일서버
15. 이용약관/개인정보처리방침 한국어 버전
16. FMP 402 에러 근본 해결
17. 모바일 반응형 전체 점검
18. 에러 페이지 (404, 500)
19. 배포 (Vercel + Railway)

### 🟢 P3 — 런칭 후
20. Detail 페이지 7개 섹션 완성
21. 브라우저 푸시 알림
22. Intraday 스캐너 인터랙션

## 유저 플로우 자동 테스트 방안
OAuth 설정 완료 후 → Claude in Chrome MCP + user-tester agent로 6개 플로우 자동 테스트 가능.
상세: `~/.claude/projects/-Users-seanbae-Desktop---/memory/qa_bug_log.md` 하단 참조.

## 코드 정리 완료 (2026-04-14)
- `framer-motion`, `lightweight-charts` npm 패키지 제거
- `risk_models.py` 하단 80줄 self-test 코드 제거
- 미사용 shadcn 컴포넌트 9개, 미사용 hooks 8개, 미사용 types 13개 → 다음 세션에서 파일 삭제 가능 (현재는 참조만 기록)

## 메모리 파일 위치
모든 프로젝트 지식은 `~/.claude/projects/-Users-seanbae-Desktop---/memory/` 에 저장:
- `qa_bug_log.md` — 버그 17개 + 출시 전 작업 23개 + 유저플로우 테스트 방안
- `product_features.md` — 기능 맵
- `design_system.md` — 디자인 가이드
- `project_tech_decisions.md` — 기술 결정사항
- `security_checklist.md` — 보안 체크리스트
- `legal_compliance.md` — 법적 컴플라이언스
- 기타 20+ 메모리 파일 (MEMORY.md에서 인덱스 확인)
