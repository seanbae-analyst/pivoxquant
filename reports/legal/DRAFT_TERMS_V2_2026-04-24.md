# DRAFT V2 — 이용약관: KIS 계좌 연동 + AI 면책 조항 (Option C 반영)

**작성일**: 2026-04-24
**상태**: 로펌 검토 전 **2차 초안** (LAW FIRM REVIEW PENDING)
**버전**: V2 (V1 = `DRAFT_TERMS_AI_CLAUSE_2026-04-23.md`, 보존)
**주요 변경**: Option C (Alpaca 제거 + KIS 단일 연동 유지) 확정에 따른 조항 재정리
**삽입 위치**: 기존 `frontend/src/app/terms/page.tsx` 의 6조(Limitation of Liability) **이후**, 7조(Changes to Terms) **이전**에 신규 7조~16조로 삽입
**적용 대상**: Journal Companion / KIS 계좌 연동 / 모든 AI 기반 출력물
**언어 원칙**: 한글+영문 병기. 동등 효력 선언은 **§16 Governing Language** 에 명시.

> **법적 고지 (초안 전용)**: 본 문서는 변호사 검토 전 내부 draft 입니다. 외부 공개·배포·프로덕션 반영 금지. 불공정약관규제법 저촉 가능성은 변호사 검토 필수.

---

## 7. Journal Companion 의 본질 (Nature of Journal Companion)

**[한글]**
(근거: 자본시장법 제6조 제2항 "투자자문업" 정의)

Journal Companion 은 이용자 본인이 작성한 기록(투자 일지, IPS 선언 등)을 **기억하여 재표시**하고, 이용자 본인의 과거 **거래 패턴을 숫자로 미러링**하며, 이용자가 스스로에게 던질 만한 **질문을 제시**하는 도구입니다.

**Journal Companion 은 자본시장법 제6조 제2항에서 정의하는 "투자자문업"이 아닙니다.** 회사는 특정 금융투자상품에 대한 매매·보유·운용에 관한 자문·조언·권유·제안을 제공하지 않습니다.

**[English]**
Journal Companion is a tool that (a) remembers and replays the user's **own** records, (b) mirrors the user's **own** past trading behavior as numbers, and (c) prompts the user with self-directed questions. Journal Companion **does not constitute "investment advisory business"** as defined in Article 6(2) of the Financial Investment Services and Capital Markets Act ("FSCMA").

---

## 8. 권유 금지 선언 (No Solicitation)

**[한글]**
(근거: 자본시장법 제9조 제1항 제23호 "투자권유", 제11조 무허가 금융투자업 금지)

PivoxQuant 서비스(Journal Companion 포함)는 아래 행위를 **어떠한 형태로도 수행하지 않습니다.**

1. 특정 종목·증권·파생상품에 대한 **매수·매도·보유·환매 제안**
2. 종목에 대한 **분석·평가·등급 부여**로서의 투자권유
3. **가격 목표·손절가·익절가**의 계산 또는 제시
4. **시장 방향·경기·업종**에 대한 **예측·전망**
5. **포트폴리오 구성·배분·리밸런싱**에 관한 제안
6. "recommend / suggest / should / advise / advice / 추천 / 조언 / 권장 / 유망" 등의 자문성 어휘 출력

만약 이용자가 직접 자문을 요청하는 경우, 서비스는 "답변할 수 없다"는 취지로 거부 응답을 제공합니다.

**[English]**
Legal basis: FSCMA Arts. 9(1)(23) and 11. PivoxQuant (including Journal Companion) will **not** provide buy/sell/hold/redeem suggestions, security analysis as solicitation, price targets, stop-loss/take-profit calculations, market or sector forecasts, or portfolio construction advice. Advisory-like vocabulary (e.g., "recommend," "should," "advise") is filtered at output.

---

## 9. AI 의 본질적 한계 (Inherent Limitations of AI)

**[한글]**
(근거: 민법 제750조 불법행위 + 소비자기본법 제19조 사업자의 의무 관련 적정 고지)

서비스의 AI 기반 출력물은 대규모 언어모델(Large Language Model) 기반이며, 아래와 같은 **본질적 한계**를 가집니다.

1. **환각 (Hallucination)**: 실재하지 않는 사실을 실재하는 것처럼 출력할 수 있습니다.
2. **부정확한 기억 재구성**: 이용자 원본 기록을 요약·인용하는 과정에서 원문과 달라질 수 있습니다.
3. **모델 버전 비결정성**: 동일 입력에 대해 세션마다 다른 응답을 생성할 수 있습니다.
4. **시점 오류**: 모델 학습 시점 이후의 정보가 반영되지 않을 수 있습니다.

이용자는 AI 응답을 판단의 근거로 삼기 전 **본인의 원본 기록 또는 원출처 데이터를 직접 확인할 의무**가 있습니다.

**[English]**
AI outputs are LLM-based and subject to hallucination, paraphrasing drift, non-determinism across sessions, and knowledge-cutoff errors. Users must verify the source record or original data before relying on any output.

---

## 10. 책임의 한계 (Limitation of Liability — AI & Data-specific)

**[한글]**
(근거: 민법 제393조 손해배상 범위, 약관규제법 제7조 면책조항 유효성)

모든 투자 결정 및 그 결과에 대한 책임은 **전적으로 이용자 본인**에게 있습니다. 회사는 다음에 대하여 어떠한 책임도 부담하지 않습니다.

1. 이용자의 **투자 손익**
2. 이용자의 **세금·수수료·환차손** 기타 금전적 결과
3. AI 응답의 **환각·부정확성**으로부터 파생된 결과
4. 제3자 서비스 제공자(Anthropic PBC, 한국투자증권, 시장 데이터 제공자, Railway, Vercel, Stripe 등)의 **서비스 중단·지연·데이터 오류**로부터 파생된 결과
5. 이용자가 **본인의 증권사 앱/웹**에서 독립적으로 수행한 매매의 결과 (본 서비스는 주문 기능 미제공, §11 참조)

단, **약관규제법 제7조** 및 관련 법령에 의해 본 조항의 전부 또는 일부가 무효로 판정되는 경우, 회사의 책임은 관련 법령이 허용하는 최대 한도로 제한됩니다.

**[English]**
All investment decisions and outcomes are the sole responsibility of the user. The Company disclaims liability for trading losses, taxes/fees/currency losses, hallucination-derived damages, and third-party outages (including but not limited to Anthropic PBC, Korea Investment & Securities (KIS), market data providers, Railway, Vercel, and Stripe) — as well as any trade the user independently places through their own brokerage app/web (the Service does not provide order execution; see §11). This disclaimer is subject to the Act on the Regulation of Terms and Conditions.

---

## 11. 계좌 연동 서비스 — 한국투자증권(KIS) 조회 전용 (Account Linking — KIS Read-Only)

> **[신규 V2]** Option C 반영. Alpaca 연동 조항 전면 삭제, KIS 단일 조회 전용 연동만 유지.

**[한글]**
(근거: 자본시장법 제6조 제1항 제2호·제3호(투자매매업·투자중개업) 비해당 선언, 전자금융거래법 제2조·제21조 안전성 의무)

### 11.1 연동 범위 — 조회 전용 (Read-Only Only)

1. PivoxQuant 는 이용자가 **본인 명의로 보유한** 한국투자증권(KIS) 계좌에 대해, KIS Open API 를 통한 **조회 전용(read-only) 연동**만을 제공합니다.
2. 본 서비스는 **매매 주문(매수·매도·정정·취소·예약주문 포함) 기능을 제공하지 않습니다.** 주문 실행 경로는 서버 코드 수준에서 차단되어 있습니다 (증거: `kis_service.py` L341~378 주문 함수 disabled).
3. 이용자는 본인 명의 KIS 계좌에 대한 정보(잔고·포지션·보유 종목·주문 체결 이력 등)만 조회할 수 있으며, **타인 명의 계좌 연동은 금지**됩니다.
4. 실제 매매는 이용자가 **본인의 KIS 앱/웹(한국투자증권 공식 채널)** 에서 독립적으로 수행하여야 합니다.

### 11.2 API 키 보관 및 보안

1. 이용자의 KIS API App Key / App Secret 은 **AES-256 이상**의 암호화 방식으로 DB 에 저장됩니다.
2. 회사는 이용자의 API 키를 **제3자에게 제공하지 않으며**, 내부 접근은 감사 로그(audit log)로 기록됩니다.
3. 이용자는 언제든 `/settings/integrations` 에서 연동을 **즉시 해제**할 수 있으며, 해제 시 API 키는 DB 에서 **즉시 물리 삭제**됩니다 (백업은 30일 내 완전 파기).
4. 이용자의 KIS API 키가 유출된 것으로 의심되는 경우, 이용자는 **KIS 홈페이지에서 즉시 키를 재발급**하고 PivoxQuant 에서도 연동을 재등록하여야 합니다.

### 11.3 투자중개업·투자매매업 비해당

회사는 자본시장법 제6조 제1항 제2호(투자매매업) 및 제3호(투자중개업)에서 정의하는 **"금융투자상품의 매도·매수·중개·주선·대리"를 수행하지 않습니다.** 이용자와 KIS 간 매매 계약은 전적으로 이용자 본인과 KIS 사이에 직접 성립하며, PivoxQuant 는 그 과정에 개입하지 않습니다.

**[English]**
### 11.1 Scope — Read-Only
PivoxQuant provides **read-only** account-linking exclusively with Korea Investment & Securities (KIS) via the KIS Open API. The Service does **not** provide order execution (buy/sell/modify/cancel/reserved orders), which is disabled at the server code level. Users may view only their **own** KIS account information. All actual trading must be executed by the user independently through the official KIS app/web.

### 11.2 API Key Storage & Security
User KIS API App Key / App Secret are encrypted at rest (AES-256 or stronger). The Company does **not** share keys with any third party. Users may disconnect at `/settings/integrations` at any time, triggering immediate DB deletion and backup purge within 30 days.

### 11.3 Not a Broker-Dealer or Intermediary
The Company does not perform any activity that constitutes "investment dealing business" (FSCMA Art. 6(1)(2)) or "investment brokerage business" (Art. 6(1)(3)). All trading contracts are formed directly between the user and KIS, with no intermediation by PivoxQuant.

---

## 12. 시세 정보 이용 제한 (Market Data Usage Restrictions)

> **[신규 V2]** KIS Open API 약관상 "시세정보 제3자 제공 금지" 조항 대응.

**[한글]**
(근거: 한국투자증권 Open API 이용약관 제4조~제6조 시세정보 이용 제한, 저작권법 제4조 편집저작물 보호, 거래소 시장정보 배포기준)

1. KIS Open API 를 통해 이용자에게 제공되는 **실시간/지연 시세 정보, 호가 정보, 체결 정보, 차트 데이터**는 오직 **이용자 본인의 열람 목적**으로만 이용됩니다.
2. 이용자는 다음 행위를 **엄격히 금지**합니다.
   - 시세 정보를 제3자(타인, 타 서비스, 커뮤니티, SNS 등)에게 공유·배포·전달하는 행위
   - 시세 정보를 자동화 도구·스크립트로 대량 추출(scraping)하는 행위
   - 시세 정보를 상업적 목적으로 재가공·재판매하는 행위
3. 제3자 데이터 제공처(FMP, SEC EDGAR, Naver 금융 등)에서 수집된 정보 역시 각 제공처의 이용약관에 따라 **본인 열람 목적**으로 제한됩니다.
4. 이용자가 위 의무를 위반하여 발생한 모든 법적·금전적 책임(KIS, 한국거래소, 기타 데이터 제공처로부터의 청구 포함)은 전적으로 **이용자 본인**이 부담합니다.

**[English]**
Market data (real-time/delayed quotes, order book, executions, charts) obtained via the KIS Open API and third-party data providers (FMP, SEC EDGAR, Naver Finance, etc.) is provided **solely for the user's personal viewing**. Users are strictly prohibited from (a) sharing/distributing/forwarding data to any third party, (b) bulk scraping via automated tools, or (c) commercial redistribution or resale. Any liability arising from breach — including claims by KIS, KRX, or any data provider — is borne entirely by the user. Legal basis: KIS Open API Terms Arts. 4-6; Copyright Act Art. 4; KRX market data distribution rules.

---

## 13. 투자자문 아님 (Not Investment Advice) — 통합 재확인

> **[신규 V2]** §7/§8 조항을 이용자 관점에서 1-문단으로 재요약.

**[한글]**
(근거: 자본시장법 제6조 제2항(투자자문업), 제18조(인가), 제101조의2(유사투자자문업))

1. **PivoxQuant 는 자본시장법상 "투자자문업" 인가를 받은 사업자가 아닙니다.**
2. 회사는 유사투자자문업 신고를 진행 중이거나 완료한 상태이며, **불특정 다수 대상의 일방향 정보 제공** 범위 내에서만 서비스를 운영합니다 (등록번호: ________ / 또는 "신고 진행 중").
3. 서비스에서 제공되는 **모든 분석·시그널(POSITIVE/NEGATIVE/NEUTRAL)·지표·리포트·AI 응답**은 **정보 제공 및 교육 목적**이며, 특정 종목의 매매 권유가 아닙니다.
4. 투자 결정과 그 결과(손익·세금·기회비용 포함)는 **전적으로 이용자 본인**에게 귀속됩니다.
5. BUY / SELL / HOLD 라벨, 특정 가격대 추천, 종목별 자문은 서비스 전 영역에서 **제공되지 않습니다**.

**[English]**
PivoxQuant is **not** a licensed investment advisory firm under FSCMA Art. 18. The Company operates within the scope of a Similar Investment Advisory Business registration (FSCMA Art. 101-2) [Reg. No. ____ / "Application in progress"], providing one-way information to an unspecified audience. All signals (POSITIVE/NEGATIVE/NEUTRAL), indicators, reports, and AI outputs are for **information and education only** and do **not** constitute a recommendation to buy, sell, or hold. Investment decisions and outcomes rest solely with the user. BUY/SELL/HOLD labels, specific price recommendations, and per-user advisory are **not** offered anywhere in the Service.

---

## 14. Closed Beta 조건 (Beta Program)

**[한글]**
(근거: 약관규제법 제6조 공정성, 민법 제390조 채무불이행)

서비스 일부 기능(Journal Companion, KIS 연동 등)은 Closed Beta 기간 중 **무상 또는 시험 가격**으로 제공되며, 회사는 다음 권리를 유보합니다.

1. **사전 고지 없이** 기능을 변경·중단·제한할 권리
2. **Beta 참여자를 선별·제한**할 권리 (연령·지역·이용 이력 기준)
3. Beta 기간 중 수집된 로그를 **품질 개선 및 규제 대응** 목적으로 이용할 권리 (마케팅 프로파일링 제외)
4. Beta 종료 시 유료 플랜으로 전환 또는 기능 종료를 결정할 권리

Beta 기간 중 발생한 이용자 피해에 대한 회사의 책임은 **§10 (책임의 한계)** 에 준하되, 약관규제법이 허용하는 최대 한도로 제한됩니다.

**[English]**
Select features are provided free or at a trial price during Closed Beta. The Company reserves the right to modify/suspend/terminate features without prior notice, to select/restrict beta participants, to use logs for quality and regulatory purposes (excluding marketing profiling), and to transition to paid plans or sunset features. Liability during beta is capped per §10, subject to the Act on the Regulation of Terms and Conditions.

---

## 15. 분쟁 해결 (Dispute Resolution)

**[한글]**
(근거: 민사소송법 제8조 관할, 국제사법 제27조 소비자계약 특례)

본 약관 및 PivoxQuant 서비스 이용에 관한 분쟁은 **대한민국 법**을 준거법으로 하며, **서울중앙지방법원**을 제1심 전속 합의 관할 법원으로 합니다. 다만, 소비자기본법 및 국제사법상 소비자 보호 규정이 우선 적용되는 경우 이용자 주소지 법원 관할이 인정될 수 있습니다.

**[English]**
Governing law: Republic of Korea. Exclusive jurisdiction: Seoul Central District Court as court of first instance, subject to mandatory consumer-protection rules under the Framework Act on Consumers and the Act on Private International Law.

---

## 16. 조항의 독립성 및 언어 효력 (Severability and Governing Language)

**[한글]**
본 약관의 일부 조항이 무효·취소·집행불가로 판정되더라도, 그 외의 조항은 계속 유효합니다 (약관규제법 제16조).

본 약관은 한글본과 영문본으로 작성되며, 양자 간 해석상 차이가 있는 경우 **한글본이 우선**합니다.

**[English]**
If any provision is held invalid, unenforceable, or void, the remaining provisions shall remain in full force and effect (Art. 16 of the Act on the Regulation of Terms and Conditions). In case of discrepancy between Korean and English versions, **the Korean version shall prevail**.

---

**본 초안 종료. 로펌 검토 후 최종본에서 조항 번호 재정리 예정.**

## 부록 A. 기존 조 번호 재정렬 매핑 (V2)

| 기존 (terms page V0) | V1 (2026-04-23) | **V2 (2026-04-24, 본 문서)** |
|---|---|---|
| 1. Acceptance | 1 (유지) | 1 (유지) |
| 2. Description | 2 (유지) | 2 (유지) |
| 3. Not Financial Advice | 3 (유지) | 3 (유지) — §13 에서 재확인 |
| 4. User Accounts | 4 (유지) | 4 (유지) |
| 5. Acceptable Use | 5 (유지) | 5 (유지) |
| 6. Limitation of Liability (general) | 6 (유지) | 6 (유지) |
| — | 7. Nature of Journal Companion | **7. 유지** |
| — | 8. No Solicitation | **8. 유지 (주어를 "PivoxQuant 서비스" 로 확대)** |
| — | 9. Inherent Limitations of AI | **9. 유지 (주어를 "서비스의 AI 출력물" 로 확대)** |
| — | 10. Limitation of Liability — AI-specific | **10. 재작성 (KIS·제3자 outage 명시, Alpaca 삭제)** |
| — | 11. License Status | **→ §13 으로 통합 이동** |
| — | — | **11. 계좌 연동 서비스 — KIS 조회 전용 (신규 V2)** |
| — | — | **12. 시세 정보 이용 제한 (신규 V2)** |
| — | — | **13. 투자자문 아님 — 통합 재확인 (신규 V2, 舊 §11 License Status 통합)** |
| — | 12. Beta Program | **14. 이동** |
| — | 13. Dispute Resolution | **15. 이동** |
| — | 14. Severability and Governing Language | **16. 이동** |
| 7. Changes to Terms | 15 → | 17 |
| 8. Contact | 16 → | 18 |

## 부록 B. V1 → V2 주요 변경점 (상세는 CHANGELOG 참조)

1. **[삭제]** Alpaca / 미국 페이퍼 트레이딩 / autotrader 관련 전 조항 (V1 에 실제 명시는 없었으나, "제3자 outage" 표현에 Alpaca 가 포함되어 있던 부분 제거 → `kis_service`, `Anthropic` 등으로 대체)
2. **[신규]** §11 계좌 연동 서비스 — KIS 조회 전용 (read-only 선언, API 키 보안, 투자중개업 비해당)
3. **[신규]** §12 시세 정보 이용 제한 (KIS Open API 약관 준수, 제3자 제공 금지)
4. **[재작성]** §10 책임의 한계 — 제3자 제공자 목록을 KIS·Anthropic·Railway·Vercel·Stripe 로 명시, "이용자 본인 증권사 앱에서의 독립 매매 면책" 신설
5. **[재확인]** §13 투자자문 아님 — 舊 §11 License Status 를 이용자 관점에서 재작성
6. **[주어 확대]** §8·§9 에서 "Journal Companion" → "PivoxQuant 서비스 전체 / AI 출력물 전체" 로 확대
