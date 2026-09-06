# 온보딩 문항 경쟁 조사 — 한국 매매일지 · 해외 트레이딩 저널 · 로보어드바이저/브로커

> 작성: 2026-09-06 · 대상: 배상현(CEO) · 확인일 전부 2026-09-06
> 방법: 앱스토어 설명·스크린샷 OCR·리뷰 전수, **배포 중인 프론트 번들·공개 API 직접 추출**,
> Form ADV·규제 PDF·원논문 PDF. 검색 요약·SEO 블로그는 1차 자료와 충돌하면 죽였다.
> 원본 증거: `onboarding-research-assets_2026-09-06/` (스크린샷 18장, PDF 2건)
> 선행 문서: `onboarding-questionnaire-v3_2026-09-06.md` (7문항 제안) — 이 조사가 그 제안을 어떻게 바꾸는지는 §6.

---

## 0. 한 줄 결론

**투자 기록앱은 한국·해외 모두 온보딩에서 성향을 묻지 않는다 (0~2문항).** 묻는 쪽은 로보어드바이저·브로커(5~11문항)인데, 그건 적합성 규제용이고 재산·경험·지식을 묻지 행동은 안 묻는다. **"왜 그렇게 매매했나"를 묻는 온보딩은 조사 범위 27개 서비스 중 하나도 없다.** 그 자리가 비어 있다. 다만 자기보고 성향 설문의 예측력은 학계·규제·업계 3면에서 약하다고 판정돼 있어, 문항은 **예측 도구가 아니라 나중에 되비출 자기 진술**로만 써야 근거와 제약(§101, 점수화 폐기)이 동시에 성립한다.

---

## 1. 문항 수 한눈에

| 서비스 | 유형 | 온보딩 문항 수 | 성향/심리 문항 | 건너뛰기 | 근거 등급 |
|---|---|---|---|---|---|
| 살래말래 (KR) | 매매일지 | **0** (일지 이름·카테고리만) | 없음 | — | 스크린샷 5장·리뷰 전수 |
| 개미의 투자일기 (KR) | 매매일지 | 확인 불가 (첫 실행 자료 없음) | 기록 시점 감정 태그 `불안`/`공포` | — | 스크린샷 6장 |
| 투자일기 (KR) | 매매일지 | **0** (4버튼 런처) | 없음 | — | 스크린샷 3장 |
| 투자노트 (KR) | 매매일지 | **0** | 없음 (`매수 메모 작성률` 지표) | — | 스토어 설명 |
| 존버노트 / Toffs / 수익차곡 (KR) | 매매일지 | **0** | 없음 | — | 스토어·리뷰 |
| 키움 자동일지 | 증권사 기능 | **0** (기준일 1개) | 없음 | — | HTS 도움말 |
| TradeZella (US) | 트레이딩 저널 | **6** | 없음 (경력·자금출처·브로커·상품·목표·유입경로) | **불가** | 앱 번들 + 공개 API |
| TraderSync (US) | 트레이딩 저널 | **1** (자산군) | 없음 | — | 배포 청크 |
| TradesViz / Tradervue / Trademetria / StonkJournal | 트레이딩 저널 | **0** | 없음 | — | 가입 HTML·번들 |
| Edgewonk (DE) | 심리 특화 저널 | 확인 불가 (Cloudflare) | **온보딩엔 없음** — Tiltmeter도 유저 자작 코멘트 사전 | — | 공식 블로그 |
| Sharesight / Kubera | 포트폴리오 | **0** (Sharesight는 세금 거주국 1개) | 없음 | — | 가입 HTML·번들 |
| 토스증권 별지 제1호 | 증권사 적합성 | **9** | 손실감내도·수익태도 | 정보 미제공 선택 가능 | 공식 PDF |
| 한국투자증권 | 증권사 적합성 | **9** | 손실감내도·투자목적 | 〃 | 공식 페이지 |
| 금융투자교육원 표준형 | 교육용 예시 | **7** | 손실감내도 | — | 공식 페이지 |
| 유안타 / 다올 | 증권사 적합성 | **10 / 11** | 〃 | — | 공식 페이지 |
| 핀릿 "금융 MBTI" (KR) | 성향 진단 | 미공개 ("5분") | 4축 % + 유형 라벨 + 상품 추천 | — | 스크린샷 4장 |
| Betterment (US) | 로보 | 실질 **2~3** (목표유형·시점·슬라이더) | **심리측정형 없음** | — | Form ADV 2026-07 |
| Wealthfront (US) | 로보 | **5** | −10% 시나리오 1개 | — | 라이브 번들 |
| Schwab (US) | 브로커 RTQ | **7** | −25% 시나리오 1개 | 시간축 <3점이면 중단 | 공식 PDF (2012) |
| Nutmeg / Moneyfarm (UK) | 로보 | **9 / 9** 리커트 | 전부 심리 진술문 | — | 2차 (~2017), 노후 |
| Robinhood / Public / Webull | 브로커 | 확인 불가 | FINRA 2111 항목 | — | 지원문서만 |
| 파운트 / 핀트 / 쿼터백 | 로보 | 확인 불가 | 설문 존재만 확인 | — | — |

**분포**: 기록앱 0~2 · 로보/브로커 5~11 · **3~5문항짜리는 아무도 없다.** 이 빈 구간이 PivoxQuant v3(7문항)의 자리다. 단 7은 기록앱 기준으로는 이례적으로 무겁다.

---

## 2. 한국 서비스 — 원문

### 2.1 살래말래 (PivoxQuant 컨셉 최근접)
- 앱 설명: *"매수/매도 근거를 기록하고 반복되는 실수를 줄이며, 더 나은 투자 판단을 만들어보세요."*
- 실제 첫 질문 = 일지 생성 모달 하나: `작성 날짜` / `매매일지 이름` / `오늘 카테고리 [국내주식][해외주식][암호화폐]` → `작성 시작`
- 기록 폼: `종목명 · 수익률 · 수량 · 매수가 · 매도가 · 수익금 · 매매 근거 (진입/청산 이유를 입력하세요)`
- 홈: `출석 체크 · Streak 2🔥 · 연속 2일 참여 중 · 다음 리워드까지 5일 남았습니다` ← **스트릭·리워드 넛지. 반면교사.**
- 리뷰 4건: "일기처럼 쓸수있어서 좋아요" / "로그인이 안됨 다튕김"(1점)

### 2.2 개미의 투자일기 — 감정 태그를 쓰는 유일한 한국 사례
- 설명: *"왜 샀고, 그때 어떤 마음이었는지 매매의 '이유'를 남겨 … 감정이 아니라, 기록으로."*
- 상단 고정 배너: `투자 원칙 1. 분할 매수/매도 한다.` ← **유저가 쓴 원칙을 앱이 판단 없이 상시 되비춤. 온보딩 문항 1개로 쓸 만한 유일한 후보.**
- 주간 회고: `매도 2건 · 불안 1건 +3,475,000원 · 공포 1건 +2,000,000원` ← 감정은 온보딩이 아니라 **기록 시점 태그**
- 면책: *"본 앱은 투자 정보를 기록·관리하는 도구이며, 특정 종목 추천이나 수익을 보장하지 않습니다."*

### 2.3 투자노트 — `매수 메모 작성률`
*"월별 수익률, 보유 집중도(HHI), 매수 메모 작성률 등 투자 습관을 돌아볼 수 있는 지표"* — 성과가 아니라 **기록 행위 빈도**를 지표화. 점수화 폐기 제약과 충돌하지 않는 유일한 벤치마크 지표.

### 2.4 증권사 적합성 설문 — 토스증권 별지 제1호 (9문항, 원문)
1. [소득상태] 향후 고객님의 연간수입원에 대한 예상은 어떻게 되십니까?
2. [투자자금의 비중] 총 자산대비 금융자산의 비중은 어느 정도 입니까? (5%~30% 초과)
3. [투자경험] 투자경험이 있는 금융투자상품과 투자경험기간 (중복)
4. [투자 수익 및 위험에 대한 태도] 원금보존이 더 중요 / 투자수익이 더 중요 / 손실 위험이 있더라도 투자수익
5. [기대수익률 및 손실감내도] 시중금리 수준 ~ 원금 초과 손실까지 감수
6. [금융지식 수준/이해도]
7. [파생상품 투자경험]
8. [취약 금융소비자 확인]
9. [유효기간 설정 동의]
→ 1~6 합산 35점 → 안정형/안정추구형/위험중립형/적극투자형/공격투자형.

**증권사 5개 사 전 문항 통틀어 "왜 그렇게 매매했나" 류 행동 문항 0개.** 전부 소득·자산·경험·지식. 이건 자본시장법 적합성 원칙용 설문이지 자기관찰 설문이 아니다. 복사할 이유가 없고, 복사하면 투자권유 서비스로 오인된다.

의뢰 전제 정정: "협회 표준 문항 원문 1종"은 **없다.** 별지 번호만 공통, 문항·배점·결과 라벨은 회사 자율 (7/9/9/10/11).

### 2.5 핀릿 "금융 MBTI" — 절대 따라하면 안 되는 것
`적극형 63% / 비유동성 50% / 분산형 60%` → `가치 발견자 AIDG` → `추천 포트폴리오`. 점수화 + 라벨링 + 상품 추천 3연타. PivoxQuant 제약 전부 위반.

---

## 3. 해외 트레이딩 저널 — 원문

### 3.1 TradeZella — 유일하게 제대로 된 온보딩 설문 (6문항, 배포 번들 `vhi=6`)
```
Welcome to Tradezella — The only tool you need to become a profitable trader.

Q1 How long have you been trading?         < 1 year / 1-3 / 3-5 / 5+   (앱이 Newbie·Climbing Ranks·Ninja Level·Monk Mode 라벨을 붙임)
Q2 What do you use to Trade:               Personal Capital / Prop Firm Account / I haven't started yet
Q3 Who is your primary broker?             드롭다운 + Other
Q4 What are you currently trading?         Stocks / Options / Forex / Crypto / Futures / CFD / Other
Q5 What are you looking to do with Tradezella?
     Journal activities — Track and document every trade
     Analyze performance — Dive deep into stats and metrics
     Backtest strategies — Test ideas with historical data
     Learn with Zella University
Q6 How did you hear about us?              Twitter / Instagram / YouTube / TikTok / Discord / Reddit / Google / ...
```
- `Select all that apply` / `Select only one` / `Continue`(선택 0개면 disabled) / **Skip 없음** / 완료 후 `/auth/payment`
- 답변 용처(코드 확인): 6문항 전부 **Customer.io 마케팅 속성으로 전송**. 제품 개인화 근거는 Q3·Q4뿐. 즉 결제 전 리드 세그멘테이션.
- 심리는 온보딩이 아니라 **일일 프롬프트**: `How do you feel about this trading day?` + 😭😞😐🙂😍 + `Add a note (optional)` (500자)

### 3.2 TraderSync — "Survey" 스텝에 질문 0개
- 유일 문항: `Select your Assets` (Stocks/Forex/Futures/Options/Crypto)
- `POST /onboard/survey` body = `{}`. 이름만 설문.
- 카피: *"Your Trading Has a Leak. We Find It."* / *"Eliminate costly mistakes."* ← 효능 과장. 톤 참고 금지.
- ❌ 죽인 주장: "trading style / primary markets / account type을 묻는다"(SEO 블로그) — 실제 코드에 없음.

### 3.3 TradesViz / Tradervue / Trademetria / StonkJournal — 가입 폼이 전부
TradesViz 자백: *"The default for all new accounts is US/Eastern as timezone and USD as currency … you can change the settings here"* → **묻지 않고 기본값 + 나중에 설정**이 업계 표준.

### 3.4 Edgewonk — 심리 특화 저널조차 온보딩에서 심리를 안 묻는다
Tiltmeter 작동 조건: *"you must create trade entry, exit, and trade management comments in your settings and rate each entry positive, negative, or neutral"* — 심리 지표가 **유저 자작 라벨 사전**에 의존. 초기 세팅 1~2시간(리뷰). 심리 데이터는 "쓰면서 쌓는 것"으로 설계.

---

## 4. 로보어드바이저·브로커 — 원문과 설계 논리

### 4.1 Betterment — 리스크 퀴즈를 사실상 폐기 (Form ADV 2026-07-31)
> "six categories – education, retirement, emergency fund, major purchase, general investing, and SDI"
> "solicits input on a client's anticipated time horizon, in conjunction with the advice type"
> "interactive slider … until they find the allocation that has the expected range of growth outcomes they are willing to experience"
→ 목표유형 1 + 시점 1 + **유저가 직접 미는 슬라이더**. 심리측정형 문항 없음. 등급 없음.

### 4.2 Wealthfront — 5문항 (라이브 번들)
1. How old are you?
2. What do you want from your investments? — grow without too much risk / as much as possible / Something in between
3. What's your annual income before taxes?
4. How much do you have in cash or assets that can easily be converted into cash?
5. **Imagine you started with a $10,000 investment. Then, in one month, your investment lost $1,000 in value. What would you do next?** — sell everything / sell some / do nothing / buy more
   부제: *"This isn't a trick question, so trust your instinct and try to answer honestly."* ← 사회적 바람직성 편향의 자백

ADV 원문 (설계 논리): *"if an individual is willing to take a lot of risk in one case and very little in another, then the individual is deemed inconsistent and is therefore assigned a lower risk tolerance score"* → 같은 개념을 두 번 물어 **불일치에 벌점**.

### 4.3 Schwab — 7문항 (공식 PDF 2012)
시간축 2문항(<3점이면 중단) + 지식 / 손익 관심 / 보유 경험 / **−25% 시나리오**(sell all 0 · sell some 2 · do nothing 5 · buy more 8) / 최선·최악 수익 범위 선택 → 2차원 매트릭스 → 5등급.

### 4.4 FINRA Rule 2111(a) — 미국 브로커 최소공배수
age · other investments · financial situation and needs · tax status · **investment objectives · investment experience · time horizon · liquidity needs · risk tolerance**. 영국 FCA는 여기에 **capacity for loss**(감내 *능력*)를 별도 축으로 요구 — "willing"과 "able"은 다르다.

---

## 5. 근거 — 자기보고 성향 설문은 얼마나 믿을 수 있나

| 판정 | 근거 | 출처 |
|---|---|---|
| 13문항 심리척도가 **단일 문항보다 낫지 않다** (주식비중 예측 β 0.343 vs 0.353, R² 0.28) | N=365 패널 6개월 | Kwak & Grable 2024, *Risks* 12:170 |
| 행동실험형(복권) 측정은 **더 나쁘다** — 측정법 간 순위상관 중앙값 r=0.11 | N=1,507 | Pedroni et al. 2017, *Nat Hum Behav* |
| 규제기관: 리스크 프로파일링 툴 **11개 중 9개 결함**. "문항이 적을수록 오분류 확률↑". "중간 선택지는 non-answer일 수 있다" | 영국 | FCA FG11/05 (2011) |
| 동일 프로필 → 로보마다 권고 주식비중 **18~100%** | 53개 로보 | Boreiko & Massarotti 2020 |
| 시나리오 문항 vs 실제: COVID −34% 폭락 때 자기주도 리테일 **83%가 거래 안 함**, 전액 현금화 **<0.5%** | Vanguard 3만 계좌 | Vanguard Research 2020-07 |
| 신념이 크게 비관화된 투자자도 **67~73%가 포트폴리오 무변경** | N=2,374 | Giglio et al. 2021, *PNAS* |
| 그래도 **손실 프레이밍·자기평가 문항이 상대적으로 낫다** (🟡 2차) | — | Guillemette et al. 2012 |
| 위기 때 변하는 건 risk tolerance가 아니라 risk perception (🟡 2차) | FinaMetrica | Roszkowski & Davey 2010 |
| 문항 수 ↔ 완료율: 15문항까지 이탈 급증 (2009~10 설문 일반) / 금융 온보딩 이탈 68% (원인 분해 없음) | — | SurveyMonkey / Signicat 2022 |

❌ 인용 금지로 죽인 수치: "폼 필드 1개당 전환율 X% 감소"(1~2/3~5/5~7/8~10pp 상충, 전부 Baymard 세탁), "핀테크 온보딩 14화면/16필드/29클릭", Grable-Lytton r=0.60, "Vanguard 11문항", TradeZella "모드 선택".

**종합**: 자기보고 설문은 예측기로는 약하지만(R² 상한 0.28) 행동과제보다는 낫고 시간적으로 안정적이다. 점수·등급 산출은 측정과학적으로도 무효 → **PivoxQuant의 점수화 폐기는 규제 회피가 아니라 근거 있는 결정.** 시나리오 문항은 예측이 아니라 **"3월에 뭐라고 답했더라"를 하락장 뒤에 되돌려 보여주는 대조 재료**로 쓸 때만 성립한다.

⚠️ 위 문헌 전부 미국·영국·독일·유럽 표본. **한국 개인투자자(고회전·단기) 데이터는 전무.** 미국 통계를 한국 유저 카피에 쓰지 말 것.

---

## 6. v3 제안(7문항)에 미치는 영향

선행 문서의 설계 원칙 — *"거울에 되비칠 수 있는 것만 묻는다"* — 는 이 조사로 **강화**된다. 조사 범위 27개 중 행동 선언을 묻는 온보딩이 0개이고, 자기보고를 "예측"이 아니라 "대조 재료"로 쓰라는 것이 근거의 결론이기 때문이다. 바꿔야 할 것은 다음 넷이다.

1. **전부 건너뛰기 가능 + "나중에 하기".** 기록앱 규범은 0~2문항이다. TradeZella처럼 Skip 없는 6문항은 결제 퍼널이라 가능했다. 무료 베타는 마찰만 남는다. 현행 skip 경로 유지.
2. **Q4·Q5(내려가면/오르면 어떻게)는 온보딩에서 빼고 pre-trade·journal 프롬프트로 옮길지 검토.** Edgewonk·TradeZella 모두 심리는 "쓰면서 쌓는" 설계다. 온보딩은 Q1(보유기간)·Q2(빈도)·Q3(종목 수)·Q6(−10% 시나리오)·Q7(기록 습관) **5문항**으로 줄이는 안이 업계 중앙값(5~7)에 맞고 기록앱 대비 마찰도 줄어든다. 단 Q4는 손절 규율 mirror의 유일한 선언 대응이므로, 빼면 D6 축은 선언 없이 관찰만 남는다 — CEO 판단.
3. **Q6 시나리오 문항은 결과 화면에서 "정답" 느낌을 주면 안 된다.** Wealthfront가 "trick question이 아니다"를 붙여야 했던 이유. 선택지 순서를 섞거나, 결과에서 이 답을 등급으로 되돌리지 말고 **문장 그대로** 보관했다가 실제 하락 뒤에 병치한다.
4. **"내 원칙 한 줄" 문항 추가 검토 (선택, 자유 텍스트).** 개미의 투자일기가 상단 배너로 상시 노출하는 패턴. 관찰 축은 없지만 pre-trade 화면에 되비출 수 있고, 판단이 들어가지 않는다. Q7과 함께 "관찰 축 없는 문항" 2개가 상한.

바꾸지 않을 것: 8코드 내부 유지 · 3버킷 노출 · 법적 확인 블록 · 원답변 JSON 보존(§5 대조 재료의 전제).

---

## 7. 카피 금지 목록 (경쟁사 실제 문장 기준)

| 금지 유형 | 시장 실제 사례 |
|---|---|
| 효능·수익 약속 | "The only tool you need to become a profitable trader" (TradeZella) · "Your Trading Has a Leak. We Find It." (TraderSync) · "늦게 시작 할 수록 당신의 수익률은 낮아집니다" · "더 이상 나에게 손절이란 없다!" (존버노트) |
| 개선 단정 | "반복되는 실수를 줄이며" (살래말래) — 권유형이라 아슬. PivoxQuant은 "줄어듭니다/좋아집니다" 단정 금지 |
| 등급·라벨·점수 | Newbie/Ninja/Monk Mode (TradeZella) · "나의 금융 DNA" 63%/AIDG (핀릿) · 안정형~공격투자형 5등급 (증권사) · Defensive~Very Adventurous 1-10 (Wealthfront) |
| 예측 주장 | "하락장에서 당신이 어떻게 행동할지" — §5 killed |
| 스트릭·리워드 넛지 | "Streak 2🔥 · 다음 리워드까지 5일" (살래말래) |
| 유입경로 문항 | "How did you hear about us?" — 유저 가치 0, 문항 수만 늘림 |
| 유일하게 안전한 톤 | *"본 앱은 투자 정보를 기록·관리하는 도구이며, 특정 종목 추천이나 수익을 보장하지 않습니다"* — 한국 기록앱 3곳이 독립적으로 채택. 온보딩 첫 화면에 동일 취지 문구 권장 |

문체: 증권사는 격식 존댓말 3인칭("고객님의 …이십니까?"). 기록앱은 **해요체 + 평서형 안내** ("진입/청산 이유를 입력하세요", "오늘의 전략을 공유해보세요"). v3 문항은 후자.

---

## 8. 열린 질문 (조사로는 못 푸는 것)

1. **한국 유저의 시나리오 응답 ↔ 실제 하락장 매매 매칭** — 세계 어디에도 공개 데이터 없음. KIS 체결내역 + 온보딩 응답으로 **PivoxQuant만 만들 수 있는 독점 데이터.** 원답변 JSON 보존이 전제.
2. **등급을 주지 않는 온보딩의 완료율** — 모든 로보가 등급을 보상으로 준다. 전례 없음. 자체 A/B(0 vs 5문항)로만.
3. 토스증권 첫 로그인 UX, 파운트/핀트/쿼터백 문항, Edgewonk 초기 설정, 개미의 투자일기 감정 taxonomy 전체 — 실기기·실계정 필요.

---

## 출처 (1차 우선)
- 살래말래 [App Store](https://apps.apple.com/kr/app/id6755510192) · [Play](https://play.google.com/store/apps/details?id=com.imgobot.stocknote&hl=ko) / 개미의 투자일기 [App Store](https://apps.apple.com/us/app/id6759135655) / 투자일기 [App Store](https://apps.apple.com/kr/app/id6749032183) / 투자노트 [Play](https://play.google.com/store/apps/details?id=app.pixelwave.investnote&hl=ko) / 핀릿 [App Store](https://apps.apple.com/kr/app/id6736693395)
- 토스증권 [투자권유준칙 별지 PDF](https://home-files.tossinvest.com/files/recommendation/투자권유준칙_별지.pdf) · [한국투자증권](https://www.truefriend.com/main/banking/Include/investDocumentCheck_in.jsp) · [금융투자교육원](https://www.kcie.or.kr/mobile/guide/24/31/web_view?content_idx=760) · [다올](https://www.daolsecurities.com/customer/investest.jspx) · [유안타](https://www.myasset.com/myasset/mall/invest/MA_1001000_T1.cmd) · [키움 0353](https://download.kiwoom.com/hero4_help_new/0353.htm)
- TradeZella [공개 옵션 API](https://api.tradezella.com/api/settings/trading_style) · [Help](https://help.tradezella.com/en/articles/13863136-getting-started-with-tradezella) / [TradesViz](https://www.tradesviz.com/blog/getting-started-with-tradesviz/) / [Tradervue](https://help.tradervue.com/article/2839-getting-started) / [Edgewonk](https://edgewonk.com/blog/10-things-to-do-in-edgewonk) / [StonkJournal](https://stonkjournal.com/)
- [Betterment ADV](https://www.betterment.com/adv) · [Wealthfront quiz](https://www.wealthfront.com/risk-questionnaire/quiz) · [Wealthfront ADV](https://www.wealthfront.com/static/documents/form_adv_part_2.pdf) · [Schwab RTQ PDF](https://www.schwab.wallst.com/schwab/retail/guidance/tools/calculators/college/resources/pdf/questionnaire.pdf) · [FINRA 2111](https://www.finra.org/rules-guidance/rulebooks/finra-rules/2111) · [FCA FG11/05](https://www.fca.org.uk/publication/finalised-guidance/fsa-fg11-05.pdf)
- [Kwak & Grable 2024](https://www.mdpi.com/2227-9091/12/11/170) · [Pedroni et al. 2017](https://gwern.net/doc/statistics/decision/2017-pedroni.pdf) · [Frey et al. 2017](https://www.science.org/doi/10.1126/sciadv.1701381) · [Boreiko & Massarotti 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7861303/) · [Pan & Statman 2012](https://www.scu.edu/media/leavey-school-of-business/finance-/statman-files/Questionnaire-JIC.pdf) · [Vanguard Cash Panickers 2020](https://mccareer.org/wp-content/uploads/2020/08/cash-panickers-coronavirus-market-volatility.pdf) · [Giglio et al. 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC7848746/) · [Guillemette et al. 2012](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2088998) · [SurveyMonkey](https://www.surveymonkey.com/curiosity/survey_questions_and_completion_rates/) · [Signicat 2022](https://www.signicat.com/the-battle-to-onboard-2022)
