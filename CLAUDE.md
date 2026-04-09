# StockPilot — Session Handoff

## 프로젝트 개요
AI + Quant 기반 개인 투자 어드바이저 플랫폼.
미국 + 한국 주식 지원. 실제 출시 목표.

## 기술 스택
- **Backend**: Flask + SQLAlchemy + SQLite
- **Frontend**: Next.js 16 + TypeScript + Tailwind + SWR
- **AI**: Claude API (Anthropic)
- **Broker**: Alpaca (US) + KIS (KR)
- **Charts**: Recharts + Lightweight Charts

## 백엔드 구조 (리팩토링 완료)
```
stockpilot/
├── app.py              # create_app() factory (189줄)
├── config.py           # Config 클래스
├── extensions.py       # db, login_manager
├── run.py              # 진입점 (port 5050)
├── models/             # SQLAlchemy 모델 (6개)
│   ├── user.py, position.py, alert.py
│   ├── signal_cache.py, trade_history.py, watchlist.py
├── routes/             # Flask Blueprint (14개)
│   ├── auth.py, portfolio.py, signals.py, market.py
│   ├── daytrade.py, alerts.py, trades.py, autotrade.py
│   ├── ai.py, watchlist.py, discover.py, realtime.py
│   ├── backtest.py, quant.py
├── services/           # 비즈니스 로직
│   ├── container.py    # 서비스 싱글턴
│   ├── serializers.py  # 모델 직렬화
│   ├── fx_service.py   # USD/KRW 환율
│   ├── cache_service.py # 시그널 캐시
│   ├── alert_service.py # 알림 생성
├── engine.py           # QuantEngine (1119줄) — 핵심 분석 엔진
├── data_fetcher.py     # 시장 데이터 (yfinance, RSS)
├── ai_service.py       # Claude API 연동
├── autotrader.py       # 자동매매 엔진
├── daytrade_service.py # 데이트레이딩
├── realtime_service.py # 실시간 가격
├── kis_service.py      # 한국 증권 API
├── backtester.py       # 백테스트
├── quant_models.py     # 고급 퀀트 모델 (StatArb, MeanReversion 등)
```

## 서버 기동
```bash
# 백엔드
cd stockpilot && python3 run.py  # port 5050

# 프론트엔드
cd stockpilot/frontend && npx next dev  # port 3000
```

## 테스트 계정
- Email: seanbae1521@gmail.com
- Password: stockpilot123

## 주요 문서
- `PRODUCT_PLAN.md` — 전체 제품 기획안 (수익 모델, 로드맵, DB 스키마)
- `frontend/CLAUDE.md` — 프론트엔드 상세 핸드오프

## 중요 원칙
- **기존 백엔드 코드 절대 건들지 말 것** — engine.py(1119줄), quant_models.py(1065줄), autotrader.py(849줄), data_fetcher.py(746줄), ai_service.py, kis_service.py, realtime_service.py, backtester.py, daytrade_service.py 등 기존 서비스 파일은 완성된 상태. 이 파일들의 로직을 수정하면 안 됨.
- **routes/, models/, services/ 구조 유지** — 리팩토링 완료된 Blueprint 구조를 깨지 말 것.
- **API endpoints 변경 금지** — 프론트엔드의 `endpoints.ts`와 백엔드의 라우트 URL이 1:1 매핑되어 있음. URL을 바꾸면 프론트/백 둘 다 깨짐.
- **UI 작업은 프론트엔드만** — 디자인 변경 시 `frontend/src/` 안의 컴포넌트만 수정. 백엔드 API 응답 구조를 바꾸지 말 것.
- **기능 추가 시 새 파일로** — 기존 파일 수정보다 새 파일 생성 우선. 기존 코드에 side effect 주지 않기.

## TODO (다음 세션)
1. [ ] **UI 디자인 시스템 교체** — **Cohere (cohere.com) 디자인 참고**:
   - 순백 배경 (#ffffff) + 진한 검정 텍스트 (회색 최소화)
   - 심플한 상단 네비바: 로고(좌) + 메뉴(중앙) + CTA(우)
   - 큰 타이틀 + 넉넉한 여백 + 깔끔한 간격
   - 밝은 섹션 ↔ 다크 섹션 교차 레이아웃
   - 메가메뉴 드롭다운 (이미지 카드 + 제품 리스트)
   - 그린 도트 상태 표시 (● READY / ● LIVE)
   - 2버튼 CTA 패턴 (채움 + 아웃라인)
   - 전체적으로 프리미엄 + 엔터프라이즈 느낌
2. [ ] **투자성향 온보딩** — 8문항 + 퀀트 프로파일 매칭
3. [ ] **인증 전환** — NextAuth.js (Google/Kakao OAuth)
4. [ ] **결제 연동** — Stripe Subscriptions
5. [ ] **실시간 자산 연동** — Alpaca/KIS 잔고 동기화
6. [ ] **테스트** — pytest + Jest + GitHub Actions CI
7. [ ] **배포** — Vercel (FE) + Railway (BE) + PostgreSQL
