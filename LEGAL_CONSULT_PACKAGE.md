# PivoxQuant 법률 자문 요청 패키지

**작성일**: 2026-04-22
**작성**: 배상현 (CEO / 개인사업자 예정)
**대상 로펌**: 김앤장 / 광장 / 태평양 핀테크·자본시장팀 (또는 준하는 전문 로펌)
**런칭 목표**: 유료 베타 → Operator 9,900 / Partner 19,900 월 구독 (Observer 0원)
**자문 희망 소요**: 1 차 검토 5~10 시간, 2 차 반영 확인 2~3 시간
**긴급도**: 중 (베타 게이트 `***REDACTED***` 로 접근 제한 중, 유료 전환 D-30 목표)

> 본 문서는 CEO 가 로펌 변호사에게 **초회 상담 시 직접 제출**하기 위해 작성한 자문 요청 패키지입니다. 각 질문에는 (a) 회사 현재 포지션, (b) 근거 증거 파일·라인번호, (c) 변호사 판단 요청 사항이 명시되어 있습니다.

---

## §0 회사 개요 (변호사 컨텍스트)

| 항목 | 내용 |
|---|---|
| 사업자 | 배상현 (개인, 1 인 창업) — 사업자등록 예정 |
| 업태/종목 | 서비스업 / 정보통신업 (SaaS) — 통신판매업 신고 예정 |
| 플랫폼 이름 | **PivoxQuant** (구 StockPilot, 2026-04-15 리브랜딩) |
| 도메인 | pivoxquant.com (가비아, 2026 년 등록) |
| 서비스 범주 | AI + 퀀트 기반 **개인투자자용 정보 제공 SaaS** |
| 대상 시장 | 한국·미국 상장 주식 (코스피/코스닥/NYSE/NASDAQ) |
| 대상 이용자 | 한국 거주 개인투자자 (영문 랜딩은 추후 해외 확장용) |
| 기술 스택 | Flask (Python) + Next.js 16 + Railway PostgreSQL + Vercel |
| 결제 | Stripe (구독, 월간) |
| 현재 상태 | 베타 (비밀번호 게이트), 유료 결제 미활성 |

### 0.1 기능 구조 요약

1. **데이터 제공** — FMP / Alpaca / KIS (read-only) / SEC EDGAR / Naver 금융 데이터 집계·시각화
2. **퀀트 분석** — 58 개 퀀트 모델 (StatArb, MeanReversion, TSMOM, ML 등) + 7-Layer Risk Defense
3. **AI 인사이트** — Claude API 기반 분석 요약·챗 (투자 **권유 금지**, 정보 해설만)
4. **리포트 산출물** — Goldman IC v2 스타일 **PDF 18 종** (Weekly Memo, Earnings Pre-Brief, Equity Research Memo 등)
5. **시그널** — POSITIVE / NEGATIVE / NEUTRAL (관찰 기반 라벨). **BUY / SELL / HOLD 라벨 절대 사용 안 함**
6. **자동매매 (autotrader.py)** — Alpaca **paper mode only**, Kill Switch + 5 Circuit Breaker, 실주문 코드 경로 완전 차단
7. **투자 성향 설문** — 20 문항, 8 개 아키타입 분류

### 0.2 명시적 금지 사항 (코드·UX 원칙)

- BUY / SELL / HOLD 직접 추천 금지 (routes / services / templates 전수 필터링)
- "매수하세요", "매도하세요", "추천", "조언" 금지
- 수익률 보장 표현 금지
- "AI Coach" 표현 금지 → "AI Assistant" 로 통일
- 모든 분석·PDF 에 면책 고지 필수

> 근거: `/Users/seanbae/Desktop/취준/stockpilot/services/legal_filter.py` (80 개 regex, 292 라인)
> `/Users/seanbae/Desktop/취준/stockpilot/CLAUDE.md` "중요 원칙" 섹션

### 0.3 가격 체계 (예정)

| 티어 | 월 구독료 (KRW, VAT 포함 여부 확인 필요) | 포함 기능 |
|---|---|---|
| Observer | 0 | 시세, 기본 차트, 주간 메모 (제한) |
| Operator | 9,900 | 전체 PDF 18 종, 퀀트 시그널, AI Chat, 7-Layer Risk |
| Partner | 19,900 | Operator + 자동매매 페이퍼 시뮬, Earnings Pre-Brief, 우선 지원 |

---

## §1 핵심 질문 (변호사 판단 필요)

### §1.1 유사투자자문업 해당 여부 ⚠ 최우선

**관련 법령**: 자본시장과 금융투자업에 관한 법률 (이하 "자본시장법") §101-2 ~ §101-8 (유사투자자문업)

**회사 현재 포지션**: **선제적 신고 예정**. 금융위원회(금감원) 유사투자자문업 신고.

**핵심 사실**:
- 당사 서비스는 **불특정 다수**에게 동일한 분석·시그널을 제공함 (개별 맞춤 자문 아님)
- 개별 종목의 **투자 판단에 관한 의견** (시그널 라벨, 퀀트 점수) 을 제공하나,
- **대가를 받고** (월 9,900 / 19,900 구독) 제공할 예정임

**증거**:
- `frontend/src/app/(dashboard)/signals/page.tsx` — POSITIVE/NEGATIVE/NEUTRAL 시그널 UI
- `engine.py` — 4-pillar scoring (Technical / Fundamental / Quant / Behavioral)
- `services/artifacts/templates/*.html` — PDF 18 종, 종목별 분석 문서

**변호사 판단 요청**:
1. 당사 서비스가 자본시장법 §101-2 ①의 **"투자판단에 관한 조언"** 에 해당하는가?
2. 시그널 라벨 (POSITIVE/NEGATIVE/NEUTRAL) 이 "조언" 의 범주에 포함되는지, 아니면 **단순 데이터 지표** 로 볼 수 있는지 경계 해석
3. 선제적 신고가 적절한 전략인지, 아니면 "정보 제공" 포지션 유지가 가능한지
4. 신고 시 대표자 결격 사유 (자본시장법 §101-3 ②) 검토 — 배상현 (1995 년생, 파산/금융사고 이력 없음)
5. 신고 수리까지 소요 시간 및 대기 중 유료 전환 가능 여부

---

### §1.2 투자자문업 / 투자일임업 해당 여부

**관련 법령**: 자본시장법 §6 ① 제5호 (투자자문업) / 제6호 (투자일임업), §18 (인가)

**회사 현재 포지션**: **해당 없음 주장**. autotrader.py 는 paper mode (모의 계좌) 로만 작동, 실주문 코드 차단.

**증거 파일·라인**:
- `/Users/seanbae/Desktop/취준/stockpilot/services/broker/user_alpaca_service.py` L109:
  `return TradingClient(self.key_id, self.secret_key, paper=True)` — **paper=True 하드코딩**
- L195: `conn.is_paper = True` — DB 에도 paper 플래그 강제
- `/Users/seanbae/Desktop/취준/stockpilot/kis_service.py` L341~378:
  - `buy_order` / `sell_order` / `_place_order` **전부 Disabled**, error 반환
  - 원본 주문 실행 로직은 L378 이하 주석 처리 상태로 보존되어 있으나 호출 경로 없음
- `/Users/seanbae/Desktop/취준/stockpilot/autotrader.py` L1305 — Kill Switch + 5 Circuit Breaker
  - position_stops / portfolio_halts / velocity_pauses / consecutive_losses / daily_reset (L235~241)

**변호사 판단 요청**:
1. Alpaca **paper mode** (모의 주문) 는 실제 자금이 움직이지 않으므로 "금융투자상품 매매" 에 해당하지 않는다는 해석이 맞는가?
2. KIS 는 read-only 주문 차단으로 자문/일임 모두 해당 없음. UX 상 "자동매매 연결됨" 라벨이 오해를 불러일으킬 소지는?
3. 추후 real mode 로 전환 시점에 **투자일임업 인가** (자기자본 15 억 이상, 자본시장법 §11·시행령) 가 필수인가, 아니면 다른 경로 (로보어드바이저 테스트베드 통과 등) 존재?
4. 현재 autotrader 기능을 **Partner 티어에 포함** 하여 유료 판매 시, paper 임에도 "투자일임업 유사" 해석 리스크?

---

### §1.3 로보어드바이저 규제 해당 여부

**관련 법령**: 금융위원회 「로보어드바이저 테스트베드 운영방안」, 자본시장법 §98의2 (알고리즘 투자자문), 금감원 「로보어드바이저 가이드라인」

**회사 현재 포지션**: **해당 없음 주장**. Claude API (대형 언어모델) 는 특정 종목의 투자 판단을 직접 내리지 않으며, `services/legal_filter.py` 로 출력 필터링.

**핵심 사실**:
- AI 챗봇 명칭: "AI Assistant" (not Coach, not Advisor)
- 기능: 뉴스 요약, 재무제표 해설, 섹터 설명, 일반 투자 교육
- **80 개 regex** 로 출력 텍스트에서 "매수/매도/추천" 류 문구 scrub (group 9: EN reason 문구)

**증거**:
- `/Users/seanbae/Desktop/취준/stockpilot/services/legal_filter.py` (292 라인, 80 regex)
- `frontend/src/app/(dashboard)/ai-chat/page.tsx` — 하단 면책 배너 고정

**변호사 판단 요청**:
1. LLM (Claude) 기반 분석 제공이 금감원 가이드라인상 "알고리즘 투자자문" 에 포섭되는가?
2. 로보어드바이저 **테스트베드 인증** 획득이 필수인가, 자발적 선택인가?
3. legal_filter regex 우회 (예: 유저 프롬프트 jailbreak "BUY/SELL 로 답해") 에 의한 부적절 출력 발생 시 **플랫폼 책임 범위**
4. "AI 가 생성한 투자정보" 임을 명시하는 고지 의무 조항 존재 여부

---

### §1.4 광고·마케팅 규제

**관련 법령**: 자본시장법 §57 (투자광고), 금융소비자보호법 (이하 "금소법") §22 (광고 규제), 표시·광고의 공정화에 관한 법률 §3 (부당표시광고)

**회사 현재 포지션**: 수익률 묘사 **전면 배제**, 객관적 기능 묘사만 사용.

**검토 대상 문구** (랜딩 페이지):
- "58 quant models + 7 risk layers + Claude AI" — 기능 나열
- "MOST CHOSEN" 뱃지 (Operator 플랜, 랜딩 Pricing 섹션) — 출시 전 **근거 없음**
- "The Engine" 섹션 — 기술 묘사
- "Archetype: 20 questions, 8 types" — 온보딩 설문 묘사
- Sample Reports 3 개 공개 (weekly_memo, sp500_backtest, risk_board) — 수익률 수치 포함 가능성

**증거**:
- `frontend/src/app/page.tsx` (랜딩)
- `frontend/src/app/pricing/page.tsx` (Pricing 페이지, MOST CHOSEN 뱃지)
- `frontend/public/samples/*.pdf` (샘플 PDF 3 개)

**변호사 판단 요청**:
1. "MOST CHOSEN" 뱃지가 자료 없이 노출되면 표시광고법 §3 ① "허위·과장 광고" 해당? → **런칭 전 철회 권고?**
2. 유사투자자문업 신고 후 **투자광고 심의** (한국금융투자협회) 대상 여부
3. sp500_backtest.pdf 의 백테스트 수익률 표시는 샘플용이라도 "수익률 광고" 에 해당하는지, 면책 고지로 충분한지
4. "58 quant models" 의 "58" 숫자 — 실제 구현 모델 수와 일치 (quant_models.py 기준 58 개 확인) 필요

---

### §1.5 금융소비자보호법 §19 — 적합성·적정성·설명의무

**관련 법령**: 금소법 §17 (적합성) / §18 (적정성) / §19 (설명의무), §22 (광고)

**회사 현재 포지션**:
- 회원가입 시 **3 필수 동의** + 1 선택 동의 (마케팅)
- 온보딩에서 **20 문항 투자자 성향 설문** → 8 개 아키타입 분류
- /pricing 결제 시 별도 **ConsentModal** (구독 반복 결제 + 14 일 환불)

**증거**:
- `frontend/src/app/(auth)/signup/page.tsx` — 3+1 체크박스
- `frontend/src/app/pricing/page.tsx` — ConsentModal (금소법 §19 대응 취지)
- `questionnaire.py` + `investor_profiles.py` — 20 문항 / 8 아키타입

**변호사 판단 요청**:
1. 정보제공형 SaaS 가 금소법 적용 대상 "금융상품판매업자등" (§2 ②) 에 해당하는지, 해당한다면 어느 조항까지 적용?
2. 20 문항 설문이 **적합성 원칙 (§17)** 의 "일반금융소비자 정보 파악" 의무에 갈음되는가?
3. ConsentModal 의 동의 항목 (구독 결제 + 자동갱신 + 14 일 환불) 이 **전자상거래법 §22의2** (정기결제 고지) 및 §17 (청약철회) 을 충족하는가?
4. 베타 (무료) 기간에는 금소법 §19 전부 또는 일부 면제 가능? (금소법 §2 ② 단서 조항 해석)

---

### §1.6 외국 금융투자상품 매매중개

**관련 법령**: 자본시장법 §6 ③ (투자중개업), 외국환거래법 §3 ③ (외국환업무), 대외무역법

**회사 현재 포지션**: **직접 주문 체결 없음**. Alpaca paper / KIS read-only 로 **체결은 전적으로 유저 측** (Alpaca / 증권사 앱).

**핵심 사실**:
- 유저가 Alpaca 계좌를 직접 보유·연결 (API 키 유저 본인이 발급)
- 당사 서버는 paper mode 로만 주문 시뮬레이션
- KIS 는 계좌번호 연동 후 **read-only** (조회만, 주문 차단)

**증거**:
- `services/broker/user_alpaca_service.py` L109 — `paper=True` 하드코딩
- `kis_service.py` L341~378 — 주문 경로 전면 disabled

**변호사 판단 요청**:
1. 유저가 이미 Alpaca (미국 브로커) 계좌를 보유하고, 당사는 API 키를 매개로 정보를 표시할 뿐이라면 **투자중개업** 에 해당하지 않는다는 해석이 맞는가?
2. KIS 계좌번호 노출 (대시보드 `/settings` 에 마스킹 표시) 시 **전자금융거래법** 상 개인정보 / 전자금융거래기록 보관 의무 (5 년) 적용 범위
3. 해외 브로커 API 키를 서버 DB 에 저장 (암호화) 하는 것이 **외국환거래법 §16** (지급수단·증권 등) 위반 소지?
4. 향후 KIS 주문 기능 복원 시 **전자금융업자 등록** 필요 여부

---

### §1.7 개인정보 국외이전 및 DPO 지정

**관련 법령**: 개인정보보호법 (PIPA) §28의8 (국외이전), §31 (개인정보 보호책임자)

**회사 현재 포지션**:
- privacy-ko.md 에 국외이전 대상·목적·수령인 명시
- 수령인: **Stripe (미국, 결제), Anthropic (미국, AI), Railway (미국/싱가포르, 인프라), Vercel (미국, 배포), Google / Kakao (OAuth)**
- DPO: **배상현 본인** (1 인 사업자, 겸직) — 자격 검토 필요

**증거**:
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/src/content/privacy-ko.md` (341 라인)
  - 국외이전 섹션 / DPO 섹션 / "변호사 검토 대기 중" 문구 잔존

**변호사 판단 요청**:
1. 현재 privacy-ko.md 의 국외이전 고지 방식이 **별도 동의** (§28의8 ①) 를 충족하는가, 아니면 **포괄 동의로도 가능한 예외** (③ 단서) 에 해당하는가?
2. DPO 를 CEO 본인이 겸직하는 것이 PIPA §31 상 적법한가? (개인정보처리자 규모 기준 — 매출·보유 건수)
3. 정보주체 수 1,000 명 초과 시 DPO 의무 지정 기준 (공공 50 만 건 / 민간 100 만 건) 과의 관계
4. 국외이전 계약서 (DPA — Data Processing Agreement) 를 Stripe / Anthropic / Railway / Vercel 과 체결했는지 확인 필요 — **CEO 확인 과제**

---

### §1.8 이용약관 / 개인정보처리방침 초안 검토

**파일**:
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/src/content/terms-ko.md` (243 라인)
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/src/content/privacy-ko.md` (341 라인)

**관련 법령**: 약관의 규제에 관한 법률 (이하 "약관규제법") §6 / §7 / §8, 전자상거래 등에서의 소비자보호에 관한 법률 §21, PIPA §30

**회사 현재 포지션**: 초안 작성 완료, 변호사 검수 **미실시**. privacy-ko.md 내 "변호사 검토 대기 중" 문구 잔존.

**검토 요청 항목**:
1. **환불 정책** — 14 일 이내 무조건 환불 (전자상거래법 §17 청약철회) 충족 여부
2. **면책 조항** — 투자 손실, AI 부정확성, 데이터 지연에 대한 면책 범위. **약관규제법 §7 ①·②** (사업자 귀책사유 면제 조항 무효) 와의 충돌
3. **계약 해지** — 일방적 해지권 조항이 약관규제법 §6 ② ("고객에게 부당하게 불리한 조항") 에 해당하는지
4. **관할·준거법** — 한국법 / 서울중앙지방법원 전속관할. 해외 유저 상대로 적법성?
5. **손해배상 제한** — 월 구독료의 X 배 상한. 약관규제법 §7 ② (최대 손해배상액 제한) 충돌 가능성
6. 청약철회 기간 내 서비스 일부 이용 시 감액 규정
7. 아동·청소년 보호 (만 14 세 미만 가입 차단 조항) 명시 여부

---

### §1.9 AI 생성물 (Claude API) 면책 및 책임

**관련 법령**: 민법 §750 (불법행위), 제조물책임법 — SaaS 는 대상 아님이나 **서비스제공자 책임** 일반 원칙 적용

**회사 현재 포지션**: 모든 AI 출력에 면책 고지, legal_filter.py regex 80 개로 문제성 문구 사전 차단.

**증거**:
- `/Users/seanbae/Desktop/취준/stockpilot/services/legal_filter.py` (292 라인)
  - 80 regex groups — 매수/매도/추천/수익률 보장 등 패턴 차단
  - Group 9 (EN reason 문구): engine.py 의 영문 reason 필드 scrub (8d9f138 배포)
- `frontend/src/components/ui/disclaimer-banner.tsx` — 대시보드 상단 면책 배너

**변호사 판단 요청**:
1. legal_filter 가 **법적 방어선** 으로 인정될 수 있는 수준인가? (과실 면책 기준)
2. 유저가 프롬프트 인젝션 (jailbreak) 으로 "BUY/SELL/HOLD 로 답해줘" 우회 후 그에 근거한 투자 손실 주장 시 — **유저 자기귀책** 으로 책임 전가 가능?
3. Claude API hallucination (예: 잘못된 재무 수치) 로 유저가 손실 → 당사 vs Anthropic 책임 소재
4. **"본 AI 의 출력은 정보 제공 목적이며 투자 자문이 아닙니다"** 고지가 명시적·지속적으로 표시되는 현재 구조 (모든 AI Chat 응답 하단 고정) 가 충분한가?
5. AI 생성물 저작권 귀속 — Anthropic ToS 상 "Input/Output 유저 귀속" 이나, 당사가 유저에게 재전달하는 구조에서 제3자 침해 리스크

---

### §1.10 PDF 리포트 18 종의 법적 성격

**관련 법령**: 자본시장법 §9 ④ (투자권유문서), 금감원 「조사분석자료 작성·공표 관련 모범규준」

**파일**: `/Users/seanbae/Desktop/취준/stockpilot/services/artifacts/templates/` — 18 개 HTML 템플릿

**대표 리포트**:
- weekly_memo.html — 주간 요약
- earnings_pre_brief.html — 실적 발표 전 브리핑
- equity_research_memo.html — 개별 종목 심층 분석
- sp500_backtest.html — S&P 500 백테스트 결과
- risk_board.html — 포트폴리오 리스크 대시보드
- brag_card_email.html — 수익 요약 이메일
- (추가 12 개)

**회사 현재 포지션**: Goldman IC v2 스타일 (editorial design), **애널리스트 의견서가 아닌 자동 생성 정보 리포트**. 모든 PDF 에 `{% include '_disclaimer.html' %}` 면책 삽입.

**증거**:
- `services/artifacts/templates/_disclaimer.html` — 공용 면책 템플릿
- 18 개 리포트 중 **20/21 개 면책 포함 확인** (P1-B: brag_card_email.html 인라인 disclaimer 사용 중, `{% include %}` 통일 필요)

**변호사 판단 요청**:
1. 개별 종목 분석을 담은 equity_research_memo, earnings_pre_brief 가 자본시장법 §9 ④ **"투자권유문서"** 에 해당하는지
2. 작성자가 **투자권유대행인** 자격 (자본시장법 §51-2) 이 필요한 수준인지, 아니면 **자동 생성 정보** 로 면제되는지
3. "Goldman Sachs IC v2" 스타일 차용 — **디자인 저작권** 침해 가능성 (배치/타이포그래피/컬러 유사)
4. PDF 하단 "Prepared by PivoxQuant Research" 표기 — 허위 자격 주장에 해당?
5. sp500_backtest.pdf 의 백테스트 수익률 그래프를 고객 마케팅에 사용 시 **투자광고 심의** 필요?

---

### §1.11 백테스트 / 수익률 시뮬레이션

**관련 법령**: 자본시장법 §57 (투자광고), 금투협 「투자권유 및 광고 관련 모범규준」

**회사 현재 포지션**:
- `backtester.py` 결과는 PDF 로 유저에게 제공 (유료 티어)
- 필수 고지: **"과거 성과는 미래 수익을 보장하지 않습니다"** 하단 삽입
- 거래 비용 (transaction cost) 포함, Sharpe/Sortino/Calmar 지표 제공

**증거**:
- `/Users/seanbae/Desktop/취준/stockpilot/backtester.py`
- `services/artifacts/templates/sp500_backtest.html` + `_disclaimer.html`
- `frontend/public/samples/sp500_backtest.pdf` — **랜딩에 공개 노출 중**

**변호사 판단 요청**:
1. 백테스트 결과 공개 시 **"실제 투자 결과가 아님"** 외 추가 고지 의무 (예: "동 백테스트는 과거 X 기간의 시뮬레이션이며 거래비용 Y% 반영" 구체성)
2. 샘플 PDF 를 랜딩 페이지 비로그인 상태에서 노출하는 것이 **투자광고** 에 해당 시 한국금융투자협회 심의 필요 여부
3. 고객의 실제 포트폴리오 기반 백테스트 제공 시 "맞춤형 자문" 으로 재분류될 소지

---

### §1.12 저작권 / 상표권 / 라이선스

**관련 법령**: 상표법, 저작권법, 디자인보호법

**항목별 현황**:

| 자산 | 현황 | 리스크 |
|---|---|---|
| 상표 "PivoxQuant" | 미등록 — **CEO 확인 필요** | 타인 선점 가능성 |
| 로고 (금색 Q 심볼) | 미등록 | 디자인권 미확보 |
| 도메인 pivoxquant.com | 가비아 등록 완료 | — |
| GitHub repo (공개) | seanbae-analyst/pivoxquant | 코드 공개 여부 재검토 필요 |
| Goldman IC v2 스타일 차용 | 배치/레이아웃 유사 | 디자인 저작권 침해 가능성 |
| 폰트 Playfair Display | SIL OFL 라이선스 확인 필요 | 상업 사용 허용되나 embed 재배포 조건 확인 |
| 폰트 EB Garamond | SIL OFL | 동일 |
| 폰트 Source Serif 4 | SIL OFL | 동일 |
| 폰트 Geist / JetBrains Mono | OFL / 각사 EULA 확인 | embed 재배포 조건 |
| FMP API 데이터 | 유료 구독 ($29/월) | 재배포·파생물 조항 확인 |
| Alpaca 데이터 | 무료 | 재배포 조항 확인 |
| SEC EDGAR | 공공 도메인 | — |
| Naver 금융 (KR 가격) | 스크래핑 여부 / API 사용 확인 필요 | 저작권·서비스 이용약관 위반 가능 |

**증거**:
- `frontend/public/fonts/` — 폰트 파일들
- `data_fetcher.py` — 외부 데이터 소스
- `fmp_service.py` — FMP API 사용

**변호사 판단 요청**:
1. "PivoxQuant" 상표 출원 우선권 확보 (류 35, 42 서비스업) — 비용·기간
2. 로고 디자인권 출원 필요성 및 우선순위
3. Goldman Sachs IC v2 시각 스타일 차용이 저작권·부정경쟁방지법상 "타인의 성과물 도용" (§2 ① 카목) 에 해당?
4. FMP / Naver 데이터를 PDF 리포트에 가공·재배포하는 것이 각 서비스 ToS 위반 여부 — **CEO 가 각 ToS 를 직접 확인한 뒤 변호사에게 공유**
5. 오픈소스 라이선스 (Next.js MIT, Flask BSD, Anthropic SDK 등) 재배포 조건 일괄 점검

---

### §1.13 세법 (부가가치세·종합소득세)

**관련 법령**: 부가가치세법, 소득세법

**회사 현재 포지션**:
- 개인사업자 등록 예정 (간이 vs 일반 결정 필요)
- Stripe 결제 통해 월 구독 수령 — **부가세 포함 / 미포함** 표기 확정 필요

**변호사 판단 요청** (세무사 연계 가능성):
1. SaaS 구독 수익의 부가세 과세 여부 — **내국용역 → 10% 과세**. 가격표 9,900 / 19,900 이 세포함인가?
2. 해외 유저 (영문 랜딩 예정) 결제 시 **영세율** 적용 요건 — 국외 사업자 증명 필요
3. 간이과세 (연 매출 8,000 만 미만) vs 일반과세 전환 시점
4. Stripe 국외 송금 수수료·환차 처리 — 간이과세에서 불리할 수 있음
5. Anthropic / Railway / Vercel 해외 지출 비용의 매입세액공제 가능 여부 (대리납부 의무)

---

### §1.14 사업자등록 / 통신판매업 / 유사투자자문업 신고 순서

**회사 현재 포지션**: HANDOVER.md 작업 A/B/C 에 CEO 직접 수행 과제로 정리됨.

**예상 순서**:
1. **개인사업자 등록** (홈택스, ~30 분) — 업태: 서비스업 / 종목: 정보통신업·전자상거래업
2. **통신판매업 신고** (공정위 / 시·군·구청, ~15 분) — 간이과세자 면제 요건 확인
3. **유사투자자문업 신고** (금감원, 서류 준비 2~3 일 + 수리 2~4 주)
4. (옵션) 부가통신사업자 신고 (과기정통부) — 매출 규모에 따라

**변호사 판단 요청**:
1. 상기 순서가 적법한가? **병렬 진행 가능한 단계** 와 **선행 필수** 단계 구분
2. 유사투자자문업 신고 수리 대기 중에 **유료 전환 불가**? 베타 비용 선결제 받기 가능 여부
3. 신고 서류 중 "사업계획서 / 약관 / 개인정보처리방침" — 본 자문 결과 반영 후 제출 순서
4. 대표자 결격사유 (자본시장법 §101-3) 자가 확인 후 로펌 교차검증 요청

---

### §1.15 베타 테스트 법적 위치

**회사 현재 포지션**:
- 비밀번호 게이트 (`***REDACTED***`, 2026-04-19 rotate) 로 제한적 접근
- 베타 = **무료**, 유료 결제 미활성
- 베타 참여자 약 N 명 (추후 집계)

**변호사 판단 요청**:
1. 무료 베타 단계에서는 금소법 §19 (설명의무) / §22 (광고) 일부 면제 해석 가능?
2. 베타 이용자가 기능 오작동 (예: 자동매매 UI 토글이 paper 인데 real 로 오인) 으로 손해 주장 시 **베타 약관 면책** 유효성
3. 베타 종료 후 유료 전환 시점에 **기존 베타 유저 재동의** 필요 여부 (약관 변경 고지 §17)
4. 베타 비밀번호 `***REDACTED***` 의 우회 접근 (URL 직접 입력 등) 시 법적 책임 분배

---

## §2 파일 증거 첨부 목록

변호사에게 **패키지로 전달 예정** 파일 목록:

### 2.1 법적 문서 (검토 대상)
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/src/content/terms-ko.md` (243 라인) — 이용약관
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/src/content/privacy-ko.md` (341 라인) — 개인정보처리방침
- `/Users/seanbae/Desktop/취준/stockpilot/services/artifacts/templates/_disclaimer.html` — PDF 공용 면책 (18 리포트 공유)

### 2.2 UI 면책 / 동의 플로우 (증거)
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/src/components/ui/disclaimer-banner.tsx` — 대시보드 면책 배너
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/src/app/(auth)/signup/page.tsx` — 회원가입 3+1 동의
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/src/app/pricing/page.tsx` — 결제 ConsentModal

### 2.3 법적 방어선 (코드 증거)
- `/Users/seanbae/Desktop/취준/stockpilot/services/legal_filter.py` (292 라인, 80 regex) — 출력 필터
- `/Users/seanbae/Desktop/취준/stockpilot/kis_service.py` L341~378 — KIS 주문 비활성화
- `/Users/seanbae/Desktop/취준/stockpilot/services/broker/user_alpaca_service.py` L109, L195 — Alpaca paper=True 하드코딩
- `/Users/seanbae/Desktop/취준/stockpilot/autotrader.py` L34~241 — Kill Switch + 5 Circuit Breaker

### 2.4 데이터 출처 (라이선스 확인 대상)
- `/Users/seanbae/Desktop/취준/stockpilot/data_fetcher.py` — Alpaca/FMP 폴백
- `/Users/seanbae/Desktop/취준/stockpilot/fmp_service.py` — FMP v4 Stable
- `/Users/seanbae/Desktop/취준/stockpilot/kis_service.py` — 한국투자증권

### 2.5 서비스 구조 이해용
- `/Users/seanbae/Desktop/취준/stockpilot/CLAUDE.md` — 프로젝트 개요 (세션 핸드오프)
- `/Users/seanbae/Desktop/취준/stockpilot/HANDOVER.md` — 최신 인수인계 (2026-04-22)
- `/Users/seanbae/.claude/projects/-Users-seanbae-Desktop---/memory/legal_compliance.md` — 기존 법무 메모

### 2.6 PDF 샘플 (광고 / 투자권유문서 판단용)
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/public/samples/weekly_memo.pdf`
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/public/samples/sp500_backtest.pdf`
- `/Users/seanbae/Desktop/취준/stockpilot/frontend/public/samples/risk_board.pdf`

---

## §3 현재 확인된 법적 리스크 (내부 감사 결과)

**최신 법무 감사 판정**: **CONDITIONAL APPROVED** (2026-04-22)

### 3.1 P0 (치명) — 0 건 ✅
- 자본시장법 §6 (금융투자업 정의) 위반: **없음**
- 자본시장법 §17 (무인가 영업) 위반: **없음**
- 자본시장법 §50 (투자광고 금지사항) 위반: **없음**
- 실제 주문 체결 기능: **전면 차단 확인**

### 3.2 P1 (중간) — 4 건 잔존
| 코드 | 항목 | 상태 |
|---|---|---|
| P1-A | engine.py EN reason 문구 | **해결됨** (legal_filter group 9, commit `8d9f138` 배포) |
| P1-B | brag_card_email.html 인라인 disclaimer | **미해결** — `{% include '_disclaimer.html' %}` 통일 필요 |
| P1-C | privacy-ko.md "변호사 검토 대기 중" 문구 잔존 | **본 자문으로 해결 예정** |
| P1-D | portfolio aria-label "Buy more"/"Sell" | **미해결** — "Record additional buy/sale" 로 변경 권고 |

### 3.3 P2 (낮음) — 다수
- 사업자등록·통판신고·유사투자자문업 신고 미이행 (런칭 전 필수)
- 상표 미등록
- DPA (Data Processing Agreement) Stripe/Anthropic/Railway/Vercel 체결 여부 미확인
- 폰트 라이선스 재배포 조건 (SIL OFL) 표기 여부

---

## §4 예상 비용 / 일정

### 4.1 자문 비용 추산 (시장가 기준)
| 단계 | 소요 시간 | 예상 비용 (로펌 기준) |
|---|---|---|
| 1 차 검토 (본 자문서 기반) | 5~10 시간 | 100~300 만 원 |
| 약관 수정 반영 확인 | 2~3 시간 | 40~80 만 원 |
| 유사투자자문업 신고 대행 (옵션) | 별도 견적 | 50~150 만 원 |
| **합계** | | **190~530 만 원** |

예산 100 만 원 한도 고려 시 **선택적 자문** (§1.1 / §1.7 / §1.8 / §1.10 중심) 로 스코프 축소 가능.

### 4.2 실행 타임라인
| 단계 | 소요 | 비고 |
|---|---|---|
| 1 차 자문 수령 | 1~2 주 | |
| 약관·정책 수정 & 재검토 | 1 주 | |
| 사업자등록 / 통판신고 | 1 주 | CEO 직접 |
| 유사투자자문업 신고 | 2~4 주 | 수리 대기 |
| 유료 전환 GO | **D+5~8 주** | 신고 수리 후 |

---

## §5 결정 필요 사항 (CEO)

자문 전 / 후 의사결정 체크리스트:

### 5.1 자문 전 CEO 사전 준비
- [ ] 사업자등록 업태·종목 결정 (일반 vs 간이과세)
- [ ] "PivoxQuant" 상표 출원 여부·류 구분 (35, 42)
- [ ] FMP / Alpaca / Naver 각 서비스의 **데이터 재배포 조항** 스크린샷 수집
- [ ] Stripe / Anthropic / Railway / Vercel **DPA (Data Processing Agreement) 체결 여부** 확인
- [ ] 베타 참여 유저 수 (현재 집계) — 자문 시 scale 판단에 사용
- [ ] 대표자 결격사유 (자본시장법 §101-3) 자가 점검 (파산·금융사고 이력 등)
- [ ] 랜딩·대시보드 주요 화면 스크린샷 20~30 장 (광고 문구 판단용)

### 5.2 자문 후 실행 결정
- [ ] 유사투자자문업 **선제 신고** 확정 (vs 정보제공 포지션 유지)
- [ ] 자동매매 real mode 로드맵 — paper-only 유지 vs 투자일임업 인가 추진
- [ ] 영문 랜딩 → 해외 유저 서비스 대상 확대 시점·국가
- [ ] Beta (₩0) → Operator 9,900 전환 **D-day** (신고 수리 후)
- [ ] 법적 문서 수정 PR 생성 → Vercel / Railway 배포 일정
- [ ] "MOST CHOSEN" 뱃지 런칭 전 철회 여부
- [ ] brag_card_email.html disclaimer `{% include %}` 통일 (P1-B)
- [ ] portfolio aria-label 변경 (P1-D)
- [ ] privacy-ko.md "변호사 검토 대기 중" 문구 제거 (P1-C)

### 5.3 모니터링 지표
- 변호사 자문 이후 월 1 회 **법무 감사 재실행** (내부 agent)
- 유저 증가에 따른 DPO 의무 지정 임계치 (PIPA 100 만 건) 추적
- 광고 문구 A/B 테스트 시 부당표시광고법 검토 루프

---

## §6 첨부 · 연락처

**CEO 직접 연락**:
- 이메일: seanbae1521@gmail.com
- 도메인: pivoxquant.com
- GitHub: https://github.com/seanbae-analyst/pivoxquant (private 전환 검토 중)

**기존 감사 보고서 위치** (자문 시 요청 시 제공):
- `/Users/seanbae/Desktop/취준/stockpilot/HANDOVER.md` (2026-04-22 최신)
- `~/.claude/projects/-Users-seanbae-Desktop---/memory/legal_compliance.md` (기존 메모)

**본 패키지 작성 방식**: 내부 법무 agent (김앤장 스탠다드 프롬프트 기반) + 코드베이스 전수 감사 결과 자동 통합.

---

*본 문서는 로펌 변호사의 공식 법률 자문을 대체하지 않으며, 자문 요청을 위한 **사전 정리 자료** 입니다. 최종 판단은 반드시 자격 있는 변호사의 검토를 거쳐야 합니다.*
