# DRAFT — 이용약관: Journal Companion / AI 면책 조항

**작성일**: 2026-04-23
**상태**: 로펌 검토 전 **1차 초안** (LAW FIRM REVIEW PENDING)
**삽입 위치**: 기존 `frontend/src/app/terms/page.tsx` 의 6조(Limitation of Liability) **이후**, 7조(Changes to Terms) **이전**에 신규 7조~14조로 삽입하고 후속 조 번호 재정렬.
**적용 대상**: Journal Companion 기능 및 모든 AI 기반 출력물
**언어 원칙**: 한글+영문 병기. 동등 효력 선언은 **§14 Governing Language** 에 명시.

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

Journal Companion 은 아래 행위를 **어떠한 형태로도 수행하지 않습니다.**

1. 특정 종목·증권·파생상품에 대한 **매수·매도·보유·환매 제안**
2. 종목에 대한 **분석·평가·등급 부여**
3. **가격 목표·손절가·익절가**의 계산 또는 제시
4. **시장 방향·경기·업종**에 대한 **예측·전망**
5. **포트폴리오 구성·배분·리밸런싱**에 관한 제안
6. "recommend / suggest / should / advise / advice / 추천 / 조언 / 권장 / 유망" 등의 자문성 어휘 출력

만약 이용자가 직접 자문을 요청하는 경우, Journal Companion 은 "답변할 수 없다"는 취지로 거부 응답을 제공합니다.

**[English]**
Legal basis: FSCMA Arts. 9(1)(23) and 11. Journal Companion will **not** provide buy/sell/hold/redeem suggestions, security analysis, price targets, stop-loss/take-profit calculations, market or sector forecasts, or portfolio construction advice. Advisory-like vocabulary (e.g., "recommend," "should," "advise") is filtered at output.

---

## 9. AI 의 본질적 한계 (Inherent Limitations of AI)

**[한글]**
(근거: 민법 제750조 불법행위 + 소비자기본법 제19조 사업자의 의무 관련 적정 고지)

Journal Companion 은 대규모 언어모델(Large Language Model) 기반 도구이며, 아래와 같은 **본질적 한계**를 가집니다.

1. **환각 (Hallucination)**: 실재하지 않는 사실을 실재하는 것처럼 출력할 수 있습니다.
2. **부정확한 기억 재구성**: 이용자 원본 기록을 요약·인용하는 과정에서 원문과 달라질 수 있습니다.
3. **모델 버전 비결정성**: 동일 입력에 대해 세션마다 다른 응답을 생성할 수 있습니다.
4. **시점 오류**: 모델 학습 시점 이후의 정보가 반영되지 않을 수 있습니다.

이용자는 Journal Companion 의 응답을 판단의 근거로 삼기 전 **본인의 원본 기록을 직접 확인할 의무**가 있습니다.

**[English]**
Journal Companion is a Large Language Model (LLM)–based tool subject to hallucination, paraphrasing drift, non-determinism across sessions, and knowledge-cutoff errors. Users must verify the source record before relying on any output.

---

## 10. 책임의 한계 (Limitation of Liability — AI-specific)

**[한글]**
(근거: 민법 제393조 손해배상 범위, 약관규제법 제7조 면책조항 유효성)

모든 투자 결정 및 그 결과에 대한 책임은 **전적으로 이용자 본인**에게 있습니다. 회사는 다음에 대하여 어떠한 책임도 부담하지 않습니다.

1. 이용자의 **투자 손익**
2. 이용자의 **세금·수수료·환차손** 기타 금전적 결과
3. Journal Companion 응답의 **환각·부정확성**으로부터 파생된 결과
4. 제3자(Anthropic PBC, 시장 데이터 제공자 등) 서비스 중단·지연으로부터 파생된 결과

단, **약관규제법 제7조** 및 관련 법령에 의해 본 조항의 전부 또는 일부가 무효로 판정되는 경우, 회사의 책임은 관련 법령이 허용하는 최대 한도로 제한됩니다.

**[English]**
All investment decisions and outcomes are the sole responsibility of the user. The Company disclaims liability for trading losses, taxes, fees, currency losses, hallucination-derived damages, and third-party outages — except to the extent such disclaimer is invalidated by the Act on the Regulation of Terms and Conditions, in which case liability is limited to the maximum permitted by law.

---

## 11. 면허 상태 및 규제 포지션 (License Status)

**[한글]**
(근거: 자본시장법 제6조·제18조 등록·인가, 제101조 유사투자자문업 신고)

1. 회사는 자본시장법상 **금융투자업(투자자문업) 인가 업체가 아닙니다.**
2. 회사는 **유사투자자문업 신고** 상태 [등록번호: ________ / 또는 "신고 진행 중"]
3. Journal Companion 은 유사투자자문업 신고 범위 내에서 제공되는 **정보 제공 도구**입니다.
4. 회사가 무인가 금융투자업에 해당하는 행위를 한 것으로 판정될 경우, 이용자는 본 약관을 근거로 어떠한 투자 결정도 정당화할 수 없습니다.

**[English]**
The Company is **not** a licensed investment advisory firm under FSCMA Arts. 6 and 18. The Company holds (or is in the process of obtaining) a Similar Investment Advisory Business registration under FSCMA Art. 101 [Reg. No. ____ / "Application in progress"]. Journal Companion is offered within the scope of that registration as an information tool only.

---

## 12. Closed Beta 조건 (Beta Program)

**[한글]**
(근거: 약관규제법 제6조 공정성, 민법 제390조 채무불이행)

Journal Companion 은 Closed Beta 기간 중 **무상 또는 시험 가격**으로 제공되며, 회사는 다음 권리를 유보합니다.

1. **사전 고지 없이** 기능을 변경·중단·제한할 권리
2. **Beta 참여자를 선별·제한**할 권리 (연령·지역·이용 이력 기준)
3. Beta 기간 중 수집된 로그를 **품질 개선 및 규제 대응** 목적으로 이용할 권리 (마케팅 프로파일링 제외)
4. Beta 종료 시 유료 플랜으로 전환 또는 기능 종료를 결정할 권리

Beta 기간 중 발생한 이용자 피해에 대한 회사의 책임은 **§10 (책임의 한계)** 에 준하되, 약관규제법이 허용하는 최대 한도로 제한됩니다.

**[English]**
Journal Companion is provided free or at a trial price during Closed Beta. The Company reserves the right to modify, suspend, or terminate the feature without prior notice, to select/restrict beta participants, to use collected logs for quality and regulatory purposes (excluding marketing profiling), and to transition to a paid plan or sunset the feature at beta end. Liability during beta is capped per §10, subject to the Act on the Regulation of Terms and Conditions.

---

## 13. 분쟁 해결 (Dispute Resolution)

**[한글]**
(근거: 민사소송법 제8조 관할, 국제사법 제27조 소비자계약 특례)

본 약관 및 Journal Companion 이용에 관한 분쟁은 **대한민국 법**을 준거법으로 하며, **서울중앙지방법원**을 제1심 전속 합의 관할 법원으로 합니다. 다만, 소비자기본법 및 국제사법상 소비자 보호 규정이 우선 적용되는 경우 이용자 주소지 법원 관할이 인정될 수 있습니다.

**[English]**
Governing law: Republic of Korea. Exclusive jurisdiction: Seoul Central District Court as court of first instance, subject to mandatory consumer-protection rules under the Framework Act on Consumers and the Act on Private International Law that may confer jurisdiction on the user's domicile court.

---

## 14. 조항의 독립성 및 언어 효력 (Severability and Governing Language)

**[한글]**
본 약관의 일부 조항이 무효·취소·집행불가로 판정되더라도, 그 외의 조항은 계속 유효합니다 (약관규제법 제16조).

본 약관은 한글본과 영문본으로 작성되며, 양자 간 해석상 차이가 있는 경우 **한글본이 우선**합니다.

**[English]**
If any provision is held invalid, unenforceable, or void, the remaining provisions shall remain in full force and effect (Art. 16 of the Act on the Regulation of Terms and Conditions). In case of discrepancy between the Korean and English versions, **the Korean version shall prevail**.

---

**본 초안 종료. 로펌 검토 후 최종본에서 조항 번호 재정리 예정.**

## 부록 A. 기존 조 번호 재정렬 매핑 (참고용)

| 기존 | 신규 |
|---|---|
| 1. Acceptance | 1 (유지) |
| 2. Description | 2 (유지) |
| 3. Not Financial Advice | 3 (유지) |
| 4. User Accounts | 4 (유지) |
| 5. Acceptable Use | 5 (유지) |
| 6. Limitation of Liability (general) | 6 (유지) |
| — | **7. Nature of Journal Companion (신규)** |
| — | **8. No Solicitation (신규)** |
| — | **9. Inherent Limitations of AI (신규)** |
| — | **10. Limitation of Liability — AI-specific (신규)** |
| — | **11. License Status (신규)** |
| — | **12. Beta Program (신규)** |
| — | **13. Dispute Resolution (신규, 관할 명시 강화)** |
| — | **14. Severability and Governing Language (신규)** |
| 7. Changes to Terms | 15 (번호 이동) |
| 8. Contact | 16 (번호 이동) |
