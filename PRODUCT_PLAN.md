# PivoxQuant — Product Plan v2.0
**AI + Quant 기반 개인 맞춤형 투자 어드바이저 플랫폼**

---

## 1. 제품 비전

> "기관급 퀀트 시스템과 AI를 결합하여, 모든 개인 투자자에게 맞춤형 투자 경험을 제공한다."

PivoxQuant은 단순한 주식 분석 도구가 아니다.
**사용자의 투자 성향을 분석**하고, 그에 최적화된 **퀀트 모델 + AI 어드바이저**를 배정하여
포트폴리오를 실시간으로 관리하고, 증권사 계좌와 직접 연동하여
**분석 → 판단 → 매매 → 리밸런싱**의 전 과정을 하나의 플랫폼에서 완결한다.

### 핵심 가치
1. **Adaptive Quant Engine** — 투자성향 분석 → 퀀트 모델 15+ 지표의 가중치/TP/SL/사이징이 자동 조정. 성향이 바뀌면 엔진이 따라감. 이게 PivoxQuant의 핵심.
2. **AI × Quant 시너지** — 퀀트 스코어링이 "무엇을" 알려주고, Claude AI가 "왜, 어떻게"를 설명. 단독이 아닌 결합이 가치.
3. **Real-time Sync** — 증권사 계좌 양방향 실시간 연동 (웹에서 사면 계좌 반영, 계좌에서 사면 웹 반영)
4. **Dual Market** — 미국 + 한국 주식 동시 지원. 원화 환산 P&L.
5. **End-to-End** — 분석 → 판단 → 매매 → 리밸런싱 전 과정을 한 플랫폼에서 완결

### 경쟁사 대비 차별점
- PortfolioPilot: AI 추천은 있지만 **매매 불가 + 미국만** → 우리는 실매매 + 한국
- TradingView: 차트 최강이지만 **퀀트 자동화 없음** → 우리는 15+ 지표 자동 스코어링
- Wealthfront: 자동 리밸런싱이지만 **수동 매매 불가** → 우리는 수동 + 자동 둘 다
- 증권사 앱: 실매매는 되지만 **AI/퀀트 분석 없음** → 우리가 분석 레이어 제공

---

## 2. 사용자 플로우

### 2.1 신규 유저
```
Landing Page (/)
  → Sign Up (이메일 또는 Google/Kakao)
  → 투자성향 온보딩 (8문항)
  → 성향 프로파일 배정 (Conservative/Balanced/Growth/Aggressive)
  → 증권사 계좌 연결 (Alpaca/KIS) — 선택사항
  → 자산 자동 동기화
  → 맞춤형 대시보드
```

### 2.2 기존 유저
```
Login → Home (포트폴리오 요약 + 시장 현황 + 시그널)
  → 대시보드에서 분석/매매/리밸런싱
  → 실시간 알림 수신
```

### 2.3 성향 변경
- 무료 유저: **3회까지** 퀀트 프로파일 + AI 세팅 변경 가능
- Pro 유저: **무제한** 변경
- 변경 시: 퀀트 가중치, TP/SL 범위, 알림 빈도, AI 코칭 스타일 모두 자동 재설정

---

## 3. 투자성향 시스템

### 3.1 온보딩 질문 (8문항)

| # | 질문 | 선택지 | 영향하는 파라미터 |
|---|------|--------|-----------------|
| 1 | 투자 경험은 어느 정도인가요? | 초보 / 1-3년 / 3-5년 / 5년+ | 리스크 허용도, UI 복잡도 |
| 2 | 주요 투자 목표는? | 자산 보존 / 안정 수익 / 성장 / 공격적 성장 | 프로파일 타입 결정 |
| 3 | 포트폴리오가 -20% 하락하면? | 전량 매도 / 일부 매도 / 유지 / 추가 매수 | SL 범위, 리스크 스코어 |
| 4 | 선호하는 투자 기간은? | 단기(~3개월) / 중기(~1년) / 장기(3년+) | TP/SL, 모멘텀 가중치 |
| 5 | 관심 있는 시장은? | 미국만 / 한국만 / 둘 다 | 유니버스 설정, 환율 알림 |
| 6 | 선호하는 섹터는? (복수) | Tech / Healthcare / Finance / Energy / Consumer / 무관 | Discover 필터, AI 분석 포커스 |
| 7 | 자동 매매에 관심이 있나요? | 수동만 / 시그널 알림 / 반자동 / 완전 자동 | 오토트레이딩 설정, 알림 타입 |
| 8 | 하루에 투자에 쓸 수 있는 시간은? | 10분 이하 / 30분 / 1시간+ | 알림 빈도, 리포트 주기, 데이트레이드 노출 |

### 3.2 투자 성향 프로파일

| 프로파일 | 기술 가중치 | 펀더멘탈 가중치 | 센티먼트 가중치 | TP 범위 | SL 범위 | 최대 포지션 | AI 코칭 스타일 |
|---------|-----------|--------------|--------------|--------|--------|-----------|--------------|
| **Conservative** | 40% | 40% | 20% | +5~10% | -3~5% | 10 | 리스크 경고 중심 |
| **Balanced** | 50% | 30% | 20% | +8~15% | -5~8% | 15 | 균형 분석 |
| **Growth** | 55% | 25% | 20% | +12~25% | -8~12% | 20 | 기회 포착 중심 |
| **Aggressive** | 60% | 20% | 20% | +15~40% | -10~20% | 30 | 고수익 전략 제안 |

### 3.3 적응형 파라미터 자동 세팅
성향 프로파일이 결정되면 다음이 **자동으로** 설정됨:
- 퀀트 엔진 가중치 (기술/펀더멘탈/센티먼트 비율)
- TP/SL 범위 (목표가/손절가 계산 기준)
- 포지션 사이징 (자본 대비 최대 투자 비율)
- 오토트레이딩 공격성 (스캔 빈도, 진입 기준 점수)
- AI 코칭 톤 (보수적 vs 공격적 조언)
- 알림 빈도 (하루 1회 vs 실시간)
- Discover 스캔 필터 (ETF 중심 vs 개별주 중심)

---

## 4. 기능 목록

### 4.1 Core (Free Tier — $0)
**포트폴리오 관리**
- [x] 포지션 수동 관리 (추가/편집/삭제)
- [x] 매수/매도 기록 + 거래 내역
- [x] P&L 계산 (USD + KRW 환산)
- [x] 포트폴리오 히스토리 차트
- [ ] 투자성향 온보딩 + 프로파일 매칭
- [ ] 소셜 로그인 (Google/Kakao)

**퀀트 분석**
- [x] 15+ 지표 기반 스코어링 (Technical + Fundamental + Sentiment)
- [x] BUY/HOLD/SELL 시그널
- [x] TP/SL 자동 계산
- [x] 섹터 배분 분석
- [x] Sharpe Ratio, Max Drawdown, 연간 수익률

**시장 데이터**
- [x] US + KR 지수 실시간
- [x] 매크로 지표 (금리, 유가, 금, 비트코인)
- [x] Morning Brief
- [x] 관심종목 관리

**제한**: 3종목까지 분석, 성향 변경 3회

### 4.2 Pro ($19/month)
**AI 분석 (무제한)**
- [x] AI SWOT 분석
- [x] AI 포트폴리오 코멘터리
- [x] AI 투자 코칭 (성향 맞춤)
- [x] AI 채팅 (포트폴리오 컨텍스트)
- [x] AI 섹터 트렌드 분석
- [ ] **AI 리밸런싱 추천** (월 1회 → "NVDA 비중 줄이고 방어주 늘려라")
- [ ] **AI 모닝 브리핑 이메일** (매일 아침 시장 요약 + 내 포트폴리오 영향)
- [ ] **AI 자연어 알림** ("AAPL이 지지선 아래로 떨어지면 알려줘" 같은 자연어 조건 알림)
- [ ] **AI 위클리 트레이드 아이디어** (매주 3개 매수 아이디어를 근거와 함께 프로액티브 제안)
- [ ] **AI 월간 포트폴리오 리뷰** (성적표 — 강점/약점/개선안 + Sharpe 추이 + 동종 비교)

**고급 분석**
- [x] Discover 스캐너 (44종목 풀)
- [x] 피어 비교
- [ ] **포트폴리오 스트레스 테스트** ("2008 금융위기 시뮬레이션하면 -32% 예상")
- [ ] **종목 간 상관관계 히트맵** (분산투자 검증)
- [ ] **경쟁사 레이더 차트** (6축: 성장성/수익성/안정성/모멘텀/밸류/퀄리티)
- [ ] **PDF 월간 리포트** (Goldman 스타일 포트폴리오 보고서)
- [ ] **Monte Carlo 시뮬레이션** ("1년 후 $X~$Y 확률 85%" 확률 분포 차트 — 기관급 리스크 분석)
- [ ] **Performance Attribution** ("이번 달 수익의 62%는 NVDA, -23%는 환율" 수익 원인 분해)
- [ ] **Benchmark 비교** (S&P 500/KOSPI 대비 내 포트폴리오 성과 오버레이 차트)
- [ ] **Factor Exposure 분석** (모멘텀/가치/성장/퀄리티 팩터 노출도 시각화)
- [ ] **배당 트래커** (예상 배당금 캘린더 + 연간 배당 수익 추정 + 배당 성장률)
- [ ] **경제 캘린더** (FOMC, CPI, 고용지표 등 주요 일정 + 내 포트폴리오 영향도 분석)

**알림**
- [ ] 이메일 알림 (시그널 변경, TP/SL 도달)
- [ ] Telegram/Kakao 알림
- [ ] 기본 웹 내 알림 (이미 있음)

**기타**
- [ ] 무제한 종목 분석
- [ ] 성향 변경 무제한
- [ ] 데이터 CSV 내보내기

### 4.3 Premium ($49/month)
**자동 매매**
- [x] 오토트레이딩 (US: Alpaca Paper, KR: KIS Simulated)
- [x] 데이트레이딩 스캐너 (인트라데이 모멘텀)
- [ ] **실계좌 오토트레이딩** (Paper → Live 전환)
- [ ] **양방향 매매 동기화** (웹에서 사면 실 계좌 체결, 실 계좌에서 사면 웹 반영)
- [ ] **WebSocket 체결 알림** (주문 접수 → 체결 → 실시간 알림)

**계좌 연동**
- [ ] **Alpaca OAuth 실계좌 연결** (미국)
- [ ] **KIS 실계좌 자동 동기화** (한국)
- [ ] **잔고/보유종목 자동 불러오기** (수동 입력 불필요)

**고급 퀀트**
- [x] 백테스팅 엔진
- [x] VIX 전략
- [x] Cross-Asset 모멘텀
- [x] Statistical Arbitrage / Mean Reversion / Momentum Breakout
- [ ] **다크풀/기관 거래 추적** (SEC 13F 공시 기반 기관 매매 흐름)
- [ ] **Insider Trading 추적** (SEC Form 4 내부자 매매 공시 — CEO 자사주 매수 시 알림)
- [ ] **Options Flow 감지** (비정상 옵션 거래량 감지 — 스마트머니/기관 움직임 추적)
- [ ] **소셜 센티먼트** (Reddit/X 언급량 + 감정 분석)
- [ ] **세금 최적화 시뮬레이터** ("지금 팔면 양도세 ₩2,340,000")
- [ ] **Kelly Criterion 포지션 사이징** (수학적 최적 투자 비율 계산기)
- [ ] **멀티 포트폴리오** (은퇴용/단타용/ETF용 최대 5개 분리)

**소셜**
- [ ] **Copy Trading** (상위 유저 포트폴리오 팔로우/복사 + 리스크-조정 Leaderboard)

**API**
- [ ] 개인용 REST API 접근
- [ ] 웹훅 알림 (커스텀 자동화)

---

## 5. 기술 스택

### 현재 (구현 완료)
| 영역 | 기술 | 비고 |
|------|------|------|
| Frontend | Next.js 16 + TypeScript + Tailwind + SWR | App Router |
| Backend | Flask + SQLAlchemy (Blueprint 구조) | create_app factory |
| DB | SQLite | 로컬 개발 |
| AI | Claude API (Anthropic) | SWOT, 코칭, 채팅 |
| 차트 | Recharts + Lightweight Charts | 영역/라인 차트 |
| 브로커 US | Alpaca API | Paper Trading |
| 브로커 KR | KIS (한국투자증권) API | 시뮬레이션 |
| 에러 추적 | Sentry | 필터링 적용 |

### 목표 (출시 기준)
| 영역 | 기술 | 가격 | 이유 |
|------|------|------|------|
| DB | **PostgreSQL** (Supabase) | 무료~$25/mo | 동시 접속, Row Level Security |
| 인증 | **NextAuth.js** | 무료 | Google/Kakao OAuth + JWT |
| 결제 | **Stripe Subscriptions** | 2.9% + 30¢ | 글로벌 표준, 한국 지원 |
| 배포 FE | **Vercel** | 무료~$20/mo | Next.js 네이티브 |
| 배포 BE | **Railway** | $5/mo~ | Python, 자동 스케일링 |
| 이메일 | **Resend** | 무료~$20/mo | 트랜잭셔널 이메일 |
| 알림 | **Telegram Bot API** | 무료 | 실시간 알림 |
| 분석 | **PostHog** | 무료 | 사용자 행동, 퍼널 |
| CI/CD | **GitHub Actions** | 무료 | 자동 테스트 + 배포 |
| 디자인 | **Tremor** + 프리미엄 템플릿 | $0~$80 | 금융 대시보드 컴포넌트 |

### 월 인프라 비용 예상
| 단계 | 비용 |
|------|------|
| **개발 (지금)** | $0 (전부 무료 티어) |
| **베타 (100명)** | ~$30/mo (Supabase + Railway) |
| **출시 (1000명)** | ~$80/mo |
| **성장 (5000명)** | ~$200/mo |

---

## 6. DB 스키마

### users 테이블 확장
```sql
ALTER TABLE users ADD COLUMN risk_profile VARCHAR(20) DEFAULT 'balanced';
ALTER TABLE users ADD COLUMN profile_changes_left INTEGER DEFAULT 3;
ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(10) DEFAULT 'free';
ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(100);
ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR(100);
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN preferred_markets VARCHAR(10) DEFAULT 'both';
ALTER TABLE users ADD COLUMN preferred_sectors TEXT; -- JSON array
ALTER TABLE users ADD COLUMN auto_trade_level VARCHAR(20) DEFAULT 'manual';
ALTER TABLE users ADD COLUMN alpaca_token TEXT; -- encrypted
ALTER TABLE users ADD COLUMN kis_token TEXT; -- encrypted
```

### investment_profile 테이블 (신규)
```sql
CREATE TABLE investment_profile (
    id INTEGER PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id),
    experience_level VARCHAR(20),
    investment_goal VARCHAR(30),
    risk_tolerance INTEGER,       -- 1-10 점수
    time_horizon VARCHAR(20),
    preferred_markets VARCHAR(10),
    preferred_sectors TEXT,       -- JSON array
    auto_trade_preference VARCHAR(20),
    daily_time_available VARCHAR(20),
    -- 자동 설정되는 퀀트 파라미터
    tech_weight FLOAT DEFAULT 0.5,
    fund_weight FLOAT DEFAULT 0.3,
    news_weight FLOAT DEFAULT 0.2,
    tp_min FLOAT DEFAULT 8.0,
    tp_max FLOAT DEFAULT 15.0,
    sl_min FLOAT DEFAULT 5.0,
    sl_max FLOAT DEFAULT 8.0,
    max_positions INTEGER DEFAULT 15,
    ai_coaching_style VARCHAR(20) DEFAULT 'balanced',
    alert_frequency VARCHAR(20) DEFAULT 'daily',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### subscriptions 테이블 (신규)
```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    stripe_subscription_id VARCHAR(100),
    tier VARCHAR(10),            -- free/pro/premium
    status VARCHAR(20),          -- active/canceled/past_due
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### broker_connections 테이블 (신규)
```sql
CREATE TABLE broker_connections (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    broker VARCHAR(20),          -- alpaca/kis
    access_token TEXT,           -- encrypted
    refresh_token TEXT,          -- encrypted
    account_id VARCHAR(50),
    is_paper BOOLEAN DEFAULT TRUE,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. 수익 모델

### 가격 정책
| 티어 | 월 가격 | 연간 (20% 할인) | 타겟 유저 |
|------|--------|----------------|----------|
| **Free** | $0 | $0 | 체험, 초보 투자자 |
| **Pro** | $19 | $182/yr | 적극적 개인 투자자 |
| **Premium** | $49 | $470/yr | 전업 트레이더, 고액 자산가 |

### 수익 시뮬레이션
| 시나리오 | Free | Pro | Premium | 월 매출 | 연 매출 |
|---------|------|-----|---------|--------|--------|
| **6개월 (500명)** | 350 | 100 | 50 | $4,350 | $52,200 |
| **1년 (2,000명)** | 1,400 | 400 | 200 | $17,400 | $208,800 |
| **2년 (5,000명)** | 3,500 | 1,000 | 500 | $43,500 | $522,000 |

### 추가 수익원 (Phase 2+)
- API 접근 요금 ($99/mo — 기관/핀테크)
- 프리미엄 PDF 리포트 ($5/건)
- 세금 최적화 시뮬레이션 (Pro에 포함하되 연 10회 제한)
- 파트너 브로커 레퍼럴 수수료

---

## 8. 개발 로드맵

### Phase A: UI + 디자인 시스템 (1주)
- [ ] Tremor 또는 프리미엄 템플릿 적용
- [ ] 대시보드 완전 재디자인
- [ ] 종목 상세 페이지 고도화
- [ ] 전 페이지 일관된 디자인 시스템
- [ ] 반응형 모바일 대응

### Phase B: 투자성향 시스템 (1주)
- [ ] 8문항 온보딩 UI + 결과 화면
- [ ] investment_profile DB 테이블 생성
- [ ] 성향 기반 퀀트 파라미터 자동 설정
- [ ] 프로파일 변경 UI + 3회 제한 로직
- [ ] AI 코칭 스타일 성향 반영

### Phase C: 인증 + 결제 (1주)
- [ ] NextAuth.js 전환 (Google/Kakao OAuth)
- [ ] Stripe Checkout 연동
- [ ] 구독 관리 페이지 (업그레이드/다운그레이드/취소)
- [ ] 티어별 기능 게이팅 (Free: 3종목 제한 등)
- [ ] Stripe Webhook 처리 (결제 성공/실패/갱신)

### Phase D: 실시간 연동 (2주)
- [ ] Alpaca OAuth 실계좌 연결 플로우
- [ ] KIS 잔고/보유종목 자동 동기화
- [ ] 양방향 매매 동기화 (웹 ↔ 실 계좌)
- [ ] WebSocket 체결 알림
- [ ] 계좌 연결/해제 관리 UI

### Phase E: 고급 분석 (2주)
- [ ] Monte Carlo 시뮬레이션 (확률 분포 차트)
- [ ] Performance Attribution (수익 원인 분해)
- [ ] Benchmark 비교 (S&P 500/KOSPI 오버레이)
- [ ] Factor Exposure 분석 (팩터 노출도)
- [ ] 포트폴리오 스트레스 테스트 ("2008년 시나리오")
- [ ] 종목 간 상관관계 히트맵
- [ ] 경쟁사 6축 레이더 차트
- [ ] 배당 트래커 + 캘린더
- [ ] 경제 캘린더 (FOMC, CPI + 포트폴리오 영향)

### Phase E-2: AI 고급 기능 (1주)
- [ ] AI 자연어 알림 ("AAPL이 지지선 아래로 떨어지면 알려줘")
- [ ] AI 위클리 트레이드 아이디어 (매주 3개 매수 제안)
- [ ] AI 월간 포트폴리오 리뷰 (성적표)
- [ ] AI 리밸런싱 추천
- [ ] PDF 월간 리포트 (Goldman 스타일)

### Phase E-3: 기관급 데이터 (2주)
- [ ] Insider Trading 추적 (SEC Form 4)
- [ ] Options Flow 감지 (비정상 옵션 거래량)
- [ ] 다크풀/기관 거래 추적 (SEC 13F)
- [ ] 소셜 센티먼트 (Reddit/X 분석)
- [ ] Kelly Criterion 포지션 사이징
- [ ] 세금 최적화 시뮬레이터
- [ ] Copy Trading + Leaderboard

### Phase F: 알림 확장 (1주)
- [ ] 이메일 알림 (Resend)
- [ ] Telegram Bot 알림
- [ ] Kakao 알림톡
- [ ] AI 모닝 브리핑 이메일 (매일 아침)
- [ ] 알림 설정 관리 UI

### Phase G: 배포 + 출시 (1주)
- [ ] PostgreSQL 마이그레이션 (Supabase)
- [ ] Vercel 배포 (프론트엔드)
- [ ] Railway 배포 (백엔드)
- [ ] CI/CD (GitHub Actions)
- [ ] 테스트 (pytest + Jest)
- [ ] 도메인 + SSL
- [ ] README + API 문서
- [ ] 개인정보처리방침 + 이용약관

---

## 9. 경쟁 분석

| 서비스 | 가격 | 강점 | 약점 | PivoxQuant 차별점 |
|--------|------|------|------|-----------------|
| **PortfolioPilot** | Free/$29 | AI 추천, 통합 자산 뷰 | 미국만, 매매 불가 | 한국+미국, 실매매, 퀀트 모델 |
| **TradingView** | $15-60 | 차트 최강, 커뮤니티 | 퀀트 없음, 자동매매 없음 | 15+ 퀀트 지표 자동화 |
| **Wealthfront** | 0.25% AUM | 자동 리밸런싱, 세금 최적화 | 수동 매매 불가, 고정 전략 | 수동+자동, 맞춤 전략 |
| **Betterment** | 0.25% AUM | 간편, 자동 | 같은 약점 | 성향 기반 개인화 |
| **증권사 앱** | 무료 | 실매매, 실시간 | AI/퀀트 없음 | AI+퀀트 분석 레이어 |
| **Quantopian** (폐쇄) | — | 백테스트, 알고 트레이딩 | 사라짐 | 계승 + AI 결합 |
| **Alpaca** | 무료 API | API 매매 | 분석/UI 없음 | 올인원 UI + 분석 |

### 우리만의 킬러 피처 (경쟁사에 없는 것)
1. **투자성향 → 퀀트 엔진 자동 조정** — 핵심 차별점. 성향 분석 결과에 따라 15+ 퀀트 지표의 가중치, TP/SL 범위, 포지션 사이징, AI 코칭 톤이 전부 자동 세팅됨. Wealthfront는 고정 전략, TradingView는 수동 설정 — 우리만 "성향 바꾸면 퀀트가 따라감"
2. **한국+미국 동시 지원** — 대부분 미국만. 한국 투자자에게 양쪽 시장을 하나의 대시보드에서 원화 환산까지 제공
3. **AI + 퀀트 결합** — AI만 있거나(PortfolioPilot) 퀀트만 있거나(TradingView). 우리는 퀀트 스코어링 + AI 분석이 하나의 시그널로 합쳐짐
4. **실매매 + 분석 올인원** — 분석 앱은 매매 불가, 증권사 앱은 분석 없음. 우리는 분석→판단→매매→리밸런싱 전과정 완결
5. **성향 변경 → 퀀트 전체 재설정** — "공격형으로 바꿀래" 한마디면 TP/SL/가중치/AI톤/알림 전부 재조정. 이건 우리만의 독점 기능

---

## 10. 리스크 및 법적 고려사항

### 규제
- 투자 자문업 등록 필요 여부 검토 (금감원)
- SEC/FINRA 규정 (미국 대상 서비스 시)
- "투자 조언이 아닌 정보 제공" 면책 조항 필수
- 개인정보 처리방침 (GDPR/개인정보보호법)

### 기술 리스크
- API Rate Limit (FMP, Alpaca, KIS) — 캐싱으로 완화
- 실시간 데이터 지연 — "15분 지연 데이터" 고지
- 오토트레이딩 오류 — 일일 손실 한도 (5%) 강제 적용
- AI 환각 — "AI 분석은 참고용이며 투자 결정의 책임은 사용자에게 있음" 고지

### 보안
- 브로커 토큰 암호화 저장 (AES-256)
- HTTPS 강제
- CORS 제한
- Rate Limiting (API 남용 방지)
- SQL Injection 방지 (SQLAlchemy ORM 사용 중)

---

*문서 버전: v2.0*
*작성일: 2026-04-07*
*작성: Claude + 배상현*
*다음 업데이트: Phase A 완료 후*
