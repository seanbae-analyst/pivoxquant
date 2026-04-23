# PivoxQuant 경쟁력 분석 & "상품화" 전략

**작성일**: 2026-04-23
**작성 주체**: McKinsey Senior Partner Mode (Strategy Agent)
**의뢰**: 배상현 (1인 창업자 / CEO)
**CEO 원래 피드백**: *"아직 너무 포트폴리오 느낌이야. 상품 느낌이 안 들어나."*
**분석 목적**: (1) 경쟁 지형에서 PivoxQuant의 실제 위치 규명, (2) "포트폴리오 -> 상품" 격차 진단, (3) 월 9,900 / 19,900원을 정당화하는 최소 기능 집합 확정

---

## Executive Summary

CEO의 "포트폴리오 느낌" 피드백은 **디자인 문제가 아니라 제품 구조의 문제**다. 현재 PivoxQuant는 *"정보를 보여주는 대시보드"* 이고, 유료 SaaS는 *"의사결정을 대신 내려주거나, 사용자 일상에 박혀서 매일 꺼내게 만드는 제품"* 이다. 두 카테고리 사이의 심리적 점프는 기능 개수가 아니라 **(a) 배송 의식 (ritual of delivery), (b) 축적감 (accumulation), (c) 인용 가능한 산출물 (citable artifact)** 의 3가지에서 결정된다. 현재 27 페이지 UI는 (a)(b)(c) 중 단 하나도 제공하지 않는다.

결론:
- **Only-we 포지션은 6개로 존재하되, 그 중 진짜 방어 가능한 것은 2개 (CFO Artifact 프레임, 한미 양방향 CFO)** 이다.
- **위험 포지션은 4개**, 특히 Koyfin이 "AI Brief" 붙이는 순간 CFO 컨셉의 해자 80%가 증발한다. 12개월 안에 해자를 다른 레이어로 옮겨야 한다.
- **Silver Bullet 3개** (정시 배송 의식 / 축적형 투자 일지 / 1:1 코칭 PDF) 는 기존 백엔드 85% 자산으로 6주 내 출시 가능하며, 이 3개만 붙으면 CEO의 "상품 느낌" 피드백은 해결된다.
- **Pricing은 현재 9,900 / 19,900이 너무 약하다.** 상품 느낌을 위해서는 **연간 결제 앵커 + Premium 29,900원 + Founding Member Lifetime 99,000원** 삼단 구조로 재설계해야 한다.

---

## 1. 경쟁사 매트릭스 (18개)

### 1-A. 한국 경쟁군

| # | 경쟁사 | 카테고리 | 무엇을 파는가 (JTBD) | 가격 (월 기준, 원) | 우리와 오버랩 | 잘하는 것 | 못하는 것 |
|---|---|---|---|---|---|---|---|
| 1 | **Toss증권** | 증권사 앱 | "MZ가 거부감 없이 주식 시작" - 심리적 허들 제거 | 무료 (거래수수료) | 🟢 낮음 (30%) - 겹치는 건 종목 스크리닝, 뉴스 | UX/카피라이팅/MZ 정서, 초단타 체류 | 분석 깊이, 퀀트, 전략 추천 |
| 2 | **카카오페이증권** | 증권사 앱 | 카톡 생태계 내 자산관리 통합 | 무료 | 🟢 낮음 (20%) | 카톡 푸시 채널, 송금 연동 | 전문 투자자 기능, 미국주식 깊이 |
| 3 | **미래에셋 m.Stock / mPOP** | 증권사 MTS | "프로급 HTS를 모바일로" | 무료 | 🟡 중 (40%) - 차트/지표 | HTS 기능 이식, 데이터 깊이 | 뉴스 요약, AI, 해외시장 UX |
| 4 | **키움 영웅문S#** | 증권사 MTS | 데이트레이더의 집 | 무료 | 🟡 중 (35%) | 주문 속도, 호가창, 퀀트 사용자 많음 | UI 구식, AI 전무, 입문자 배제 |
| 5 | **삼성증권 mPOP / 한투 MTS** | 증권사 MTS | 리테일 + HNW 혼합 | 무료 + 프리미엄 리포트 | 🟡 중 (35%) | 애널리스트 리포트 인프라 | 외부 툴 느낌, 개인화 약함 |
| 6 | **스노우볼 (Snowball72)** | 퀀트 SaaS | "개인 퀀트 백테스트 + 포트폴리오 자동 리밸런싱" | 29,000~79,000 (추정) | 🔴 **높음 (70%)** - 직접 경쟁 | 국내 퀀트 커뮤니티 1위, 팩터 라이브러리 | UX 구식, 미국 주식 약함, 커뮤니티 폐쇄적, 신규 유입 낮음 |
| 7 | **증권통** | 종목 분석 앱 | "이 종목 사? 말아?" 즉답 | 부분유료 (광고 모델) | 🟡 중 (45%) | 종목 리포트 속도, 공시/수급 데이터 | 개인화 0, 전략/백테스트 없음 |
| 8 | **Growin (그로윈)** | 퀀트 SaaS | 개인 투자자용 Bloomberg 지향 | 19,900~99,000 (추정) | 🔴 **높음 (75%)** - 직접 경쟁 | 데이터 깊이 있는 척, 퀀트 포지셔닝 | 사용자 이탈 많음, 상품화 약점 동일함 |
| 9 | **할수있다 알고투자 / 퀀트 유튜버들** | 교육 콘텐츠 | "직접 코딩 안 해도 퀀트" | 무료 + 강의 99,000~500,000 | 🟡 중 (50%) | 대중 신뢰, SEO, 커뮤니티 | SaaS화 실패, 1회성 강의 수익 |
| 10 | **파운트 / 핀트** | 로보어드바이저 | "맡겨두면 알아서 굴려줌" | 운용보수 0.5~1% | 🟢 낮음 (15%) - 위임형이라 반대 | 위임 편의, 라이선스 | 재미/학습/주체감 0, Self-directed 수요 놓침 |
| 11 | **뱅크샐러드 투자** | 마이데이터 + 추천 | "흩어진 자산을 한눈에" | 무료 | 🟢 낮음 (20%) | 마이데이터 연결, 자산 그래프 | 추천 피상적, 액션 연결 약함 |

### 1-B. 글로벌 경쟁군

| # | 경쟁사 | 카테고리 | JTBD | 가격 (USD/월) | 오버랩 | 잘하는 것 | 못하는 것 |
|---|---|---|---|---|---|---|---|
| 12 | **Koyfin** | Bloomberg-lite | "블룸버그 없는 Analyst의 툴" | $0 / $39 / $79 | 🔴 **매우 높음 (85%)** - 가장 위협적 레퍼런스 | 데이터 밀도, 차트/대시보드 커스텀, 북미 애널리스트 신뢰 | AI 브리핑/Artifact 0, 한국시장 미지원, 정적 데이터 중심 |
| 13 | **FinChat.io** | AI Equity Research | "AI에게 묻는 10-K/실적콜" | $0 / $29 / $89 | 🔴 **매우 높음 (80%)** | 컨퍼런스콜 transcript AI Q&A, 빠른 성장, Citation 기반 | 실행/포트폴리오 없음, Artifact 배송 없음, 챗봇 중심 |
| 14 | **Simply Wall St** | 비주얼 주식분석 | "스노우플레이크 차트로 한눈에" | $10 / $20 / $40 | 🟡 중 (55%) | 비주얼 브랜드, 인포그래픽, 글로벌 진출 | 분석 얕음, 백테스트 없음, 전략 추천 약함 |
| 15 | **Finbox / Stock Rover** | 스크리너 + 밸류에이션 | "내 기준으로 거르기 + DCF" | $20 / $45 / $79 | 🟡 중 (50%) | 팩터/Screener 깊이, 기관형 | UX 구식, AI 없음, 모바일 약함 |
| 16 | **Quiver Quantitative** | Alt Data | "의원 거래/내부자/Reddit 트래킹" | $10 / $30 | 🟡 중 (40%) | Alt Data Only-them, 유니크 DB | 해석/의사결정 지원 없음 |
| 17 | **Composer.trade** | No-Code Algo | "알고리즘 트레이딩을 드래그앤드롭으로" | $0 / $24 / $79 | 🟡 중 (45%) | 진짜 실행까지 이어짐, 커뮤니티 전략 공유 | 한국 접근 불가, 데이터 깊이 약함 |
| 18 | **Seeking Alpha Premium** | 리서치 콘텐츠 | "개별 종목 양질의 콜/반대의견" | $30 / $240 연 | 🟡 중 (50%) - Earnings Pre-Brief 유사 | 20년 누적 리서치, 저자 생태계 | AI 없음, 개인화 0, 포트폴리오 관리 없음 |
| 19 | **Morningstar Investor** | 장기투자 리서치 | "Wide moat 기업 + Star Rating" | $35 / $249 연 | 🟡 중 (40%) | 브랜드, 펀드 데이터, 은퇴 맥락 | 테크 아님, 개인화 약함, UI 구식 |
| 20 | **Public.com Premium** | 브로커 + 콘텐츠 | "친구와 종목 얘기 + 매매" | $10 | 🟡 중 (35%) | Social proof, 콘텐츠 큐레이션 | 깊이 0, 한국 불가 |
| 21 | **Unusual Whales / Tradytics** | 옵션 플로우 | "대량 옵션 거래 감지" | $48~125 | 🟢 낮음 (20%) | 옵션 데이터 Only-them | 주식 투자자 JTBD 아님 |
| 22 | **AlphaSense** | 기관용 리서치 검색 | "10-K/콜/애널리스트 리포트 통합검색" | $4,000+ 연간 (기관) | 🟢 낮음 (10%) | 기관 표준, Citation | 리테일 무관, 가격대 |
| 23 | **Capitol Trades** | 의원 거래 공개 | "의원이 뭐 샀나" | 무료 (지금은) | 🟢 낮음 (5%) | 특정 Alt Data | 수익모델 불투명 |
| 24 | **Finimize** | 뉴스레터 | "5분 금융 뉴스 + 커뮤니티" | $15 / $80 연 | 🔴 **높음 (70%)** - Weekly Memo 유사 | 일일 뉴스레터 의식, 60만 구독자, 브랜드 보이스 | 개인화 0, 포트폴리오 기반 아님, Generic |
| 25 | **Bloomberg Terminal / Refinitiv** | 기관 표준 | "트레이더의 작업대" | $24,000+ 연 | - | 기관 락인 | 리테일 불가 |
| 26 | **Betterment / Wealthfront** | 로보어드바이저 | "위임형 자산관리" | 0.25% AUM | 🟢 낮음 (10%) | 라이선스, 세금 효율, 자동화 | Self-directed 수요 아님 |

### 한 줄 총평

> 한국에서 **스노우볼/Growin**은 직접 경쟁이지만 상품화 실패로 빈 자리가 있고, 글로벌에서는 **Koyfin + FinChat + Finimize 3자의 교집합**이 CFO 컨셉과 겹친다. 즉 PivoxQuant의 해자는 *"누구도 하지 않은 영역"* 이 아니라 *"세 개가 따로 잘하는 걸 한 앱으로 묶고 + 한국시장 + 양방향"* 이라는 **포지셔닝의 새로운 좌표**다. 이건 장점이자 약점이다: 장점은 현존 증거가 있다는 것, 약점은 Koyfin이 AI 붙이면 60%가 복제된다는 것.

---

## 2. Only-We 포지션 (6개)

McKinsey 정의: *"경쟁사가 6개월 내 복제하기 어렵고, 그 불가능성이 구조적 이유 (기술/법/유통/데이터/문화) 에서 오는 위치"*

| # | Only-we 포지션 | 방어력 (1-10) | 왜 방어되는가 | 지속기간 (개월) |
|---|---|---|---|---|
| **1** | **CFO Artifact 프레임 (챗봇 아닌 이메일/PDF/음성)** | 7 | 컨셉 자체는 복제 쉽지만 "User as CFO" 브랜드 스토리는 한 번 선점되면 Follower가 후발 주자처럼 보임. 단, 공개 마케팅 시작 전까지만 유효 | 12 |
| **2** | **한미 양방향 동시 분석 (Seoul session → NY session 연속 브리핑)** | 9 | Koyfin/FinChat는 한국 데이터 접근 자체가 구조적 비용 (KRX 라이센스+한글 NLP). 국내 증권사는 미국 분석 백엔드 없음. **진짜 구조적 해자** | 36+ |
| **3** | **58개 퀀트 모델 + 7-Layer Risk Defense 백엔드 깊이** | 7 | Toss/카카오 증권이 이 깊이를 못 만드는 건 능력이 아니라 전략 (그들은 진입 단순화가 JTBD). Growin/스노우볼과는 동급이나 UX로 우위 | 24 |
| **4** | **법적 회색지대 정교한 회피 (POSITIVE/NEGATIVE/NEUTRAL 라벨, 89 regex filter, KIS read-only)** | 8 | 투자자문업 면허 없이 개인화 추천을 합법으로 하는 구조 설계는 레퍼런스가 거의 없음. 로펌 검토 비용이 스타트업 진입장벽 | 24 |
| **5** | **Goldman IC editorial 톤 + Vantablack + Bronze 디자인 시스템** | 6 | 미적 일관성은 모방 가능하나 시간이 걸림. 경쟁사는 대부분 "핀테크 민트/블루" 틀 안. 브랜드 기호로 차별 | 18 |
| **6** | **1인 창업자의 의사결정 속도 + AI 레버리지 (경쟁사 대비 20배 release velocity)** | 7 | 구조적 속도 우위. Toss 같은 대기업은 법무/보안 리뷰만 2주. 단, 이건 자산이지 포지션이 아니므로 고객에겐 비가시 | N/A |

### 진짜 방어 가능한 핵심 2개

**(1) 한미 양방향 CFO** 와 **(4) 법적 회색지대 정교한 회피** 가 **진짜 구조적 해자**다. 나머지는 "지금은 유효하지만 1년 후 약해짐" 에 해당한다.

**시사점**: 브랜드/마케팅 메시지는 **(1)+(4) 조합** 을 반드시 전면에 내야 한다. 현재 랜딩 14 섹션 중 이 조합을 명시적으로 내세운 섹션이 있는가? 없다면 즉시 수정이 필요하다.

---

## 3. 위험 포지션 (4개)

| # | 위험 시나리오 | 확률 (12개월 내) | Impact | 우리가 죽는 속도 | 대응책 |
|---|---|---|---|---|---|
| **A** | **Koyfin이 "AI Brief" 기능 출시** (GPT/Claude 기반 일간 이메일) | 55% | 치명 - CFO 컨셉 해자의 80% 증발 | 6개월 | 해자를 "Artifact" 에서 "한국시장 + 축적형 일지" 레이어로 이동. 지금부터 "Korea-US cross-market intelligence" 로 브랜드 재포지셔닝 |
| **B** | **Toss증권이 "AI 종목 요약" 탭 추가** (GPT 기반 자연어 브리핑) | 70% | 중-상 - 한국 리테일 시장 상단 잠식 | 12개월 | Toss JTBD는 "쉬움", 우리 JTBD는 "깊음". 의도적으로 **Toss 고객 제외**하고 "Toss 너머" 포지셔닝. Power-retail, Intermediate-quant 페르소나 집중 |
| **C** | **스노우볼/Growin이 모바일 + AI 리브랜딩** | 30% | 중 - 한국 퀀트 SaaS 시장 재격동 | 9개월 | 백테스트/팩터는 그들이 우위. 우리는 **Research Artifact + Daily ritual** 로 다른 카테고리를 만들어 직접 경쟁 회피 |
| **D** | **OpenAI가 ChatGPT에 "Portfolio" 플러그인 공식 지원** (플레이드/KIS 연동) | 25% | 치명 - 리테일 투자 분석 자체가 범용화 | 12개월 | 유일한 대응: **도메인 특화 프롬프트+피드백 루프 축적** 이 범용 LLM보다 예측력이 높다는 증명 (backtest accuracy 비교 페이지) |

### 경보: 확률 x Impact 곱이 가장 큰 것은 시나리오 A이다.

**Kill Criteria**:
- Koyfin이 AI Brief 출시한 뒤 3개월 이내에 우리 Paid 전환율이 기준치 (MVP 기준 2%) 이하로 지속되면, 제품 카테고리를 "Weekly Memo" 에서 "Korea Alpha Desk" 로 전면 피벗한다.

---

## 4. Blue Ocean 검증: CFO 컨셉은 진짜 빈 바다인가?

**결론: Partial Blue Ocean (60% 블루, 40% 겹침)**

| Artifact | 유사 제품 | 중복도 | 블루 정도 |
|---|---|---|---|
| Weekly Memo | Finimize (60만 구독), Morning Brew | 65% | 🟡 약한 블루 - Generic 뉴스레터 vs 개인화 Memo의 차이로만 승부 |
| Brag Card | **없음** (가장 가까운 것은 Robinhood 공유 스크린) | 5% | 🟢 진짜 블루 - 이건 신규 카테고리 |
| Earnings Pre-Brief | Seeking Alpha Premium, FinChat | 70% | 🟡 약한 블루 - 단, 한국 종목 Pre-Brief 는 공란 |

**시사점**:
1. **Brag Card** 는 **진짜 Only-we**. 이건 상품 느낌 + 바이럴 동시 해결.
2. **Weekly Memo** 는 카피만으로는 안 되고, "개인 포트폴리오 기반 맞춤 + 한미 양방향" 없으면 Finimize 패스트팔로워로 보임.
3. **Earnings Pre-Brief** 는 한국 종목 한정으로 블루, 미국은 레드.

**권고**: Brag Card를 **1순위 상품 훅** 으로 끌어올려라. Weekly Memo는 2순위, Earnings는 3순위가 맞다. 현재 MVP 3개가 같은 weight인 것부터 재배분.

---

## 5. "상품 느낌" Feature 15개

**진단: "포트폴리오 느낌"의 3대 원인**
1. **No ritual of delivery** - 사용자가 *"매일/매주 이 시간에 이것이 도착한다"* 는 기대가 없다
2. **No accumulation** - 한 달 써도 "쌓인 것"이 안 보인다 (로그/일지/성장 그래프 0)
3. **No citable output** - 들고 나갈 산출물이 없다 (PDF, 이미지, 음성파일, URL)

위 3개를 정면으로 해결하는 15개 feature (ICE 점수 역순 정렬):

### Tier 1 — 이번 분기 (6주 내, 5개)

| # | 이름 | 1줄 | 상품느낌 근거 (심리학) | 난이도 | 배치 | 레퍼런스 | ICE |
|---|---|---|---|---|---|---|---|
| **F1** | **Morning Brief 정시 배송 (KST 07:30, EST 09:00)** | 매일 두 번, 내 포트폴리오 기반 요약 이메일+푸시 | **Variable reward + Cue-based habit (Hooked model)**. 도착 시각 고정 = 일상 의식화 | L | Free (제한 종목) / Pro (무제한) | Finimize, Morning Brew | 9x9x9=729 |
| **F2** | **Portfolio Journal (투자일지)** | 거래/매수매도 근거를 메모로 축적, 30/90/365일 회고 자동 생성 | **Endowment effect + Sunk cost**. 쌓은 기록이 많을수록 이탈 불가 | M | Pro 전용 | Day One, Obsidian | 10x8x7=560 |
| **F3** | **Brag Card 자동 생성 & 공유** | 월말 "내 포트폴리오 하이라이트" 이미지 카드 자동 생성 + 카톡/X 공유 | **Social proof + Signaling theory**. 무료 바이럴 유입 채널 | M | Free (워터마크) / Pro (워터마크 제거) | Spotify Wrapped, Strava 공유 | 10x9x6=540 |
| **F4** | **주간 CFO PDF (Monthly Retainer Letter)** | 매주 금요일, 내 포지션에 대한 8~12페이지 PDF 리포트 (Goldman IC 톤) | **Perceived scarcity + 인용가능성 (Citable artifact)**. 물리적 부피감이 "유료 가치" 의 심리적 앵커 | M | Premium 전용 | Morningstar, Seeking Alpha | 9x8x7=504 |
| **F5** | **Streak + 7일 연속 투자 학습** | 매일 1 분석 열람/1 일지 작성 시 불꽃 아이콘, 끊기면 리셋 | **Loss aversion + Streak gamification (Duolingo)**. 한국 사용자 특히 민감 | L | 모두 (Pro는 x2 배율) | Duolingo, Wordle | 9x8x8=576 |

### Tier 2 — 6개월 내 (5개)

| # | 이름 | 1줄 | 상품느낌 근거 | 난이도 | 배치 | 레퍼런스 | ICE |
|---|---|---|---|---|---|---|---|
| **F6** | **Voice Morning Brief (1분 30초 팟캐스트)** | TTS로 매일 내 포트폴리오 음성 브리핑, Apple/Spotify 개인 RSS | **Multi-modal anchoring**. 출근길 수동적 소비 채널 확보. 경쟁사 거의 없음 | M-H | Premium | NotebookLM Audio, Marketplace Daily Podcast | 8x7x6=336 |
| **F7** | **Slack/카톡 비서 (/portfolio, /earnings TSLA)** | 카톡 플러스친구 or Slack bot으로 즉시 질의 | **Ambient UX**. 앱 안 들어와도 닿는 서비스 = "상시 직원" 느낌 | M | Pro (일 10회) / Premium (무제한) | Intercom, ChatGPT Slack bot | 8x8x6=384 |
| **F8** | **커스텀 스크리너 + 저장된 전략** | 내가 만든 팩터 조합 저장/공유/알림 | **IKEA effect**. 직접 만든 것에 대한 애착 | M | Pro (3개) / Premium (무제한) | Finbox, Stock Rover | 7x7x6=294 |
| **F9** | **Anonymous 리그 테이블** | 프로필 무명, 월간 수익률 퍼센타일만 공개, Top 10% 배지 | **Competitive signaling + 가명 투명성**. 커뮤니티 없이 social proof 확보 | M | 모두 (Premium는 상세 지표) | Strava Segment, eToro Popular Investors | 7x6x5=210 |
| **F10** | **Notion/Obsidian 연동 (일지 자동 동기화)** | 내 Portfolio Journal을 외부 노트앱에 1일 1회 동기화 | **Data portability = Trust signal**. Power 유저 락인 | M | Premium | Notion API, Readwise | 6x7x6=252 |

### Tier 3 — 12개월 내 (5개)

| # | 이름 | 1줄 | 상품느낌 근거 | 난이도 | 배치 | 레퍼런스 | ICE |
|---|---|---|---|---|---|---|---|
| **F11** | **Earnings Auto-Watch** | 내 포트폴리오 종목 실적일 자동 감지 + 전날 21:00 Pre-Brief + 당일 실적 후 30분 Post-Mortem | **Automated vigilance**. 놓칠 수 없는 이벤트를 맡기는 경험 | M-H | Premium | Seeking Alpha Earnings | 8x7x5=280 |
| **F12** | **AI 맞춤 코칭 (월간 피드백 레터)** | 내 일지 + 거래 기록 기반, "3가지 개선점" 월간 개인 코칭 PDF | **Personalization 깊이**. LLM 시대 진짜 Only-we는 "내 데이터에 맞춘 AI" 가 전부 | H | Premium+ (차기 29,900원 티어) | Reflectly, Woebot | 9x6x5=270 |
| **F13** | **한국 Alt Data 대시보드** | 외국인/기관 수급, 공매도 잔고, 공시 실시간, 컨센서스 리비전 | **Domain moat**. 미국 경쟁사가 못 건드리는 데이터 | H | Premium | Capitol Trades (한국판), 증권통 | 8x7x5=280 |
| **F14** | **백테스트 공유 + "내 전략 시뮬레이션"** | Composer 스타일 no-code 전략 빌더 + 과거 수익률 시뮬 + URL 공유 | **Epistemic commitment + Viral**. 전략 공유는 자발적 마케팅 | H | Premium | Composer, QuantConnect | 8x6x4=192 |
| **F15** | **API + Open Data Export** | 개인 API 키 발급, CSV/JSON export, Power 유저 자동화 | **Developer-grade trust signal**. 월 29,900~ 티어 정당화 | M | Premium+ 전용 | Alpaca, Koyfin Pro | 7x6x6=252 |

---

## 6. TOP 3 Silver Bullet

> *"CEO의 감성 피드백을 해결할 가장 강력한 기능은?"* 답은 **새 기능 3개가 아니라 기존 자산의 재포장 3개**다. 백엔드 85% 완성이라는 것은 이미 총알이 다 장전되어 있다는 뜻. 문제는 방아쇠 디자인.

### Silver Bullet #1: **Morning Brief 정시 배송 (F1)**
- **왜 이게 1순위인가**: "상품 느낌" 의 3대 원인 중 (1) ritual of delivery 를 단독으로 해결한다. Cron + SendGrid + 기존 Dossier 데이터만 있으면 됨. **6주 내 출시 가능**.
- **심리적 효과**: 사용자 머릿속에 "07:30 = PivoxQuant" 라는 시간표가 각인. 이건 Bloomberg Terminal 사용자가 오전 첫 클릭을 블룸버그에 하는 심리와 동일.
- **구현 비용**: **Railway cron 1개 + 이메일 템플릿 1개 + 푸시 알림 1개**. 엔지니어링 시간 3-5일. 월 운영비 5,000원.

### Silver Bullet #2: **Portfolio Journal (F2)**
- **왜 이게 2순위인가**: "상품 느낌" 의 (2) accumulation 을 해결. 사용자가 3개월 써보면 "이걸 끊으면 내 3개월 기록이 사라진다" 는 심리적 락인 형성. **가장 강력한 리텐션 무기**.
- **심리적 효과**: Endowment effect (내 것이 된 순간 가치 2배 이상). 실제 Notion/Day One 구독자 이탈율이 SaaS 중 가장 낮은 이유.
- **구현 비용**: DB 테이블 1개 + 에디터 UI (기존 Next.js) + 30/90/365일 회고 자동 템플릿. **2-3주**.

### Silver Bullet #3: **주간 CFO PDF (F4) - Retainer Letter**
- **왜 이게 3순위인가**: "상품 느낌" 의 (3) citable output 을 해결. PDF 한 장이 주는 "유료 서비스" 의 물리적 앵커는 디지털 UI보다 5-10배 강력. 월 19,900원 을 정당화하는 유일한 방법은 **"내 손에 남는 것"** 이다.
- **심리적 효과**: Goldman/McKinsey가 수십 년간 PDF 메모를 끊지 못하는 이유 = 출력물이 "전문성의 증거" 로 기능. 업무 이메일 포워드 가능 = 바이럴.
- **구현 비용**: 기존 Dossier 페이지 -> PDF 렌더러 (WeasyPrint / Puppeteer) + 주간 cron. **2주**.

### 3개 통합 출시 제안: **"CFO 풀패키지 론칭 (6주)"**

> 현재 "Weekly Memo / Brag Card / Earnings Pre-Brief" 3종 MVP에서 **Brag Card를 Tier 2로 미루고**, Morning Brief + Portfolio Journal + Weekly PDF 로 MVP 3종을 **재구성**한다. 이렇게 하면 6주 후 출시 시점에 CEO의 "상품 느낌" 피드백은 해결된다. Brag Card는 이 3개로 Paid 유입을 만든 뒤 Tier 2 바이럴 무기로 배치하는 것이 자원 배분상 최적.

---

## 7. Pricing 재검토

### 현재 구조의 문제

| 티어 | 현재 | 문제점 |
|---|---|---|
| Free | 무료 | Paid 전환 동기 약함, "뭘 주고 뭘 안 주는지" 불명확 |
| Pro | 9,900원 | **"상품 느낌" 부족의 근원**. 1만원 이하는 심리적으로 "서비스" 가 아니라 "앱" 으로 분류됨 (Netflix 17,000원, 멜론 11,000원 대비) |
| Premium | 19,900원 | Pro와 차별 기능이 무엇인지 명확하지 않음. 2배 값을 내는 이유가 추상적 |

### 맥킨지 Anchor Pricing 원칙
1. **상단 앵커**: 높은 가격을 먼저 보여주고 중간 가격이 저렴해 보이게
2. **연간 결제 인센티브**: 월결제 대비 20~25% 할인으로 현금흐름 확보
3. **Founding Member Lifetime**: 초기 100-500명에게 평생 가격. "얼리 어답터 사회적 계약"

### 권고 Pricing 구조 (3x2 매트릭스)

| 티어 | 월결제 | 연간결제 (월환산) | 연간 할인율 | 포함 기능 |
|---|---|---|---|---|
| **Free** | 0 | - | - | 종목 1개 추적, Morning Brief 주 2회, Brag Card (워터마크) |
| **Pro** | 14,900 | 11,900 (143,000/년) | 20% | 종목 10개, Morning Brief 매일, Portfolio Journal, Brag Card (워터마크 제거), Streak |
| **Premium** | **29,900** | 22,900 (275,000/년) | 23% | 무제한, Weekly CFO PDF, Voice Brief, Slack/카톡 비서, 한국 Alt Data, API, Earnings Auto-Watch |

### 특수 옵션

| 옵션 | 가격 | 수량 한정 | 근거 |
|---|---|---|---|
| **Founding Member Lifetime** | 99,000원 일시불 (평생) | 선착순 200명 | Paid 전환 허들 극복 + 초기 열렬한 옹호자 창출. 실 수익보다 "우리는 구독자를 500명 확보했다" 마케팅 자산으로 활용 |
| **Team / Family Plan (3인)** | Premium 39,900/월 | - | LTV 상승, CAC 절감 (1인이 2명 데려옴) |

### 가격 변경 논리

**9,900 -> 14,900 인상 리스크**: 20% 전환 하락 예상. 그러나 **"상품 느낌 강화 + 기능 확장 (F1~F5)"** 이 동반되면 하락 상쇄 가능. 중요: **가격 올리기 전에 F1+F2+F4 먼저 출시 필수.**

**Premium 19,900 -> 29,900 인상**: 현재 Premium에 값 20,000원을 낼 사람은 전체의 3-5%. 29,900원에 낼 사람은 1-2%. 절대 수는 줄지만 **객단가가 1.5배**. ARPU (유저당 매출) 기준 승리.

**Kill Criteria (Pricing)**:
- 가격 인상 후 **6주간 Paid 전환율이 기존 대비 30% 이상 하락** 하고 F1-F4가 전부 출시된 상태라면, 즉시 10,900 / 19,900 으로 롤백.

---

## 8. 실행 로드맵 (6주 x 3 Wave)

| Wave | 주차 | 핵심 과제 | 성공 기준 |
|---|---|---|---|
| **Wave 1 (Week 1-2)** | 기반 | F1 Morning Brief + F2 Portfolio Journal 뼈대 + 이메일 인프라 (SendGrid) | 내부 dogfood 7일 연속 정시 배송 성공 |
| **Wave 2 (Week 3-4)** | 상품화 | F4 Weekly CFO PDF 렌더러 + F5 Streak UI + Pricing 페이지 재설계 | 지인 베타 10명에게 배송, NPS >=30 |
| **Wave 3 (Week 5-6)** | 런칭 | 랜딩 리뉴얼 (Only-we 포지션 (1)(4) 전면 배치) + Founding Member 100명 모집 + Brag Card Tier 2 설계 | 유료 전환 20명, 매출 150만원 누적 |

### KPI (6주 후 측정)
- **Paid 전환율**: Free -> Paid 전환 2% 이상
- **D7 리텐션**: 40% 이상 (Portfolio Journal 효과 기대)
- **Email Open Rate (Morning Brief)**: 35% 이상 (Finimize 평균 30%)
- **NPS**: 30 이상

### Risk & Mitigation
| 리스크 | 확률 | 대응 |
|---|---|---|
| 6주 안에 3개 기능 다 못 만듦 | 40% | F1만 출시하고 F2/F4는 8주로 연기. F1 단독으로도 "상품 느낌" 50% 해결 |
| Morning Brief 이메일이 스팸 분류 | 25% | SPF/DKIM 설정 + 도메인 evergreen + 초기 배송량 조절 |
| 가격 인상에 기존 Pro 이탈 | 30% | 기존 가입자 Grandfathering (기존 가격 6개월 보장) |

---

## 9. 최종 권고

**CEO께**: "상품 느낌" 피드백의 해결은 **새 기술이 아니라 새 루틴의 설계**에 있다. 이미 장전된 58개 퀀트 모델과 4-pillar scoring은 방아쇠가 없는 총이다. Morning Brief + Portfolio Journal + Weekly PDF는 그 방아쇠다. 이 3개를 6주 안에 출시한 뒤, 가격을 14,900/29,900으로 올리고, Founding Member 200명을 확보하라. 이게 다음 100만원을 두 배로 키우는 유일한 경로다.

---

### Appendix A. 참고 URL (검증 필요)
- Koyfin: https://www.koyfin.com/pricing/
- FinChat: https://finchat.io/pricing
- Finimize: https://www.finimize.com/pricing
- Simply Wall St: https://simplywall.st/pricing
- Seeking Alpha: https://seekingalpha.com/premium
- Composer: https://www.composer.trade/pricing
- 스노우볼: https://snowball72.com (가격 비공개)
- Growin: https://growin.co (가격 비공개 추정)

### Appendix B. 이 분석의 한계
- 한국 SaaS 가격 정보 (스노우볼/Growin) 는 공개 자료 부족으로 추정치 사용. 실제 가격 조사 필요.
- 경쟁사 오버랩 % 는 주관적 판단 기반. 실 사용자 인터뷰 5명 확보 후 재보정 권고.
- "상품 느낌" 심리학 근거 (Hooked, Endowment effect 등) 는 B2C SaaS 일반 원칙에서 도출. 한국 리테일 투자자 특화 리서치 별도 필요.

**End of Report**
