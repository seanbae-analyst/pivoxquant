# 신규 규제 7건 영향도 분석 (2026-04~05 스캔)

**작성일**: 2026-05-18
**원본 SoT**: `~/.claude/projects/.../memory/regulatory_changes_2026-05.md`
**스캔일**: 2026-05-10
**다음 재스캔**: 2026-08-15 (PIPA 9월 시행 직전 + 정통망법 시행령 확정 시점)
**대상**: 금융규제·자본시장법 전문 변호사

---

## 요약

- **HIGH 3건**: 정통망법 §50 6% 과징금 / 유사투자자문업 양방향 채널 / AI 생성물 표시제
- **MEDIUM 3건**: PIPA §28-8 10% 과징금 / 금소법 6대 원칙 / 전자상거래법 가분적 디지털콘텐츠
- **LOW 1건**: KRX 데이터 라이선스 (변동 없음)

**§101 면제 트랙 영향**: YES (2건 — ① 정통망법 §50 + ② 유사투자자문업 양방향 채널)
**마이데이터 영향**: NO (read-only 단일 broker)

---

## 🔴 HIGH ① — 정통망법 §50 매출 6% 과징금 신설

| 항목 | 내용 |
|---|---|
| **개정안 본회의 통과** | 2026-03-12 |
| **국무회의 의결** | 2026-03-24 |
| **시행 예상** | 2026-Q3 (공포 후 6개월) |
| **출처** | [bizgo blog](https://blog.bizgo.io/trend/telecom-business-act-amendment-spam-penalty/) / [국가법령정보센터 §50](https://www.law.go.kr/%EB%B2%95%EB%A0%B9/%EC%A0%95%EB%B3%B4%ED%86%B5%EC%8B%A0%EB%A7%9D%20%EC%9D%B4%EC%9A%A9%EC%B4%89%EC%A7%84%20%EB%B0%8F%20%EC%A0%95%EB%B3%B4%EB%B3%B4%ED%98%B8%20%EB%93%B1%EC%97%90%20%EA%B4%80%ED%95%9C%20%EB%B2%95%EB%A5%A0/%EC%A0%9C50%EC%A1%B0) |

**핵심**: 기존 과태료 + **매출액 6% 과징금** 신설. 영리목적 광고성 정보 수신 동의 위반 / opt-out 처리 시한 위반.

**PivoxQuant 영향**:
- Pro ₩9,900 / Premium ₩19,900 유료 회원 마케팅 메일 = 직접 적용 대상
- 기존 EmailSender 시스템 (services/email/sender.py:100, PR #5886fe0) 점검 필요
- **2년 주기 수신동의 재확인 자동화** 추가 필요
- **opt-out 처리 시한 (대통령령 — 통상 14일)** 준수 증거 로깅 강화

**변호사 자문 요청 포인트**:
- 시행령 확정 시 opt-out 처리 시한 정확치 확인 (Q12)
- 정보 제공 메일(Weekly Memo) vs 마케팅 메일 분류 기준
- 2년 재동의 자동화 구현 방식의 법적 충분성

---

## 🔴 HIGH ② — 유사투자자문업 양방향 채널 금지 (§101 면제 트랙 핵심)

| 항목 | 내용 |
|---|---|
| **시행** | 2024-08-14 (이미 시행 — 출시 전 재검토 트리거) |
| **출처** | [금융위 보도자료 2024-08-13](https://www.fsc.go.kr/no010101/82887) / [이투데이](https://www.etoday.co.kr/news/view/2387577) |

**핵심**: SNS / 오픈채팅방 등 **양방향 채널 + 유료 회원제 = 투자자문업 등록 의무**. 미등록 시 3년 이하 징역 / 1억원 이하 벌금.

**PivoxQuant 영향**:
- §101 면제 트랙 4요건 중 **"특정성 회피" 직접 영향**
- ✅ User as CFO 컨셉 (Artifact 일방향 푸시) = 단방향 → 안전 트랙
- ❌ 챗봇 / Q&A / "이 종목 어떤가요?" 응답 = **즉시 CRITICAL 전환**
- 현재 운영 중인 `companion`, `ai-chat`, `pre-trade` 페이지 — **양방향 해석 위험**

**변호사 자문 요청 포인트** (Q13 핵심):
- Artifact 단방향 푸시 = 양방향 채널 해당 안 됨 사인 필수
- companion / ai-chat 인터페이스 검토 — 양방향 해석 가능성
- 절대 금지 boundary: 챗봇/Q&A에서 "이 종목 매수 어떤가?" 응답 시 면제 트랙 깨짐 확인

---

## 🔴 HIGH ③ — AI 생성물 표시제 의무화

| 항목 | 내용 |
|---|---|
| **시행** | 2026-01 (이미 시행) |
| **출처** | [decentlaw 정리](https://decentlaw.io/en/news/670) / [korea.kr 공식 브리핑](https://www.korea.kr/briefing/policyBriefingView.do?newsId=156734331) / [Lexology 추천·보증 표시·광고심사지침 개정](https://www.lexology.com/library/detail.aspx?g=9726c6a7-2020-4956-836b-7cf8f3dd9bae) |

**핵심**: AI 사업자 의무 + 생성형 AI 콘텐츠·광고 = "AI 사용" 명시 필수. 워터마크 / 자막 등 명확 표시. 위반 시 표시광고법상 기만광고 → **시정명령·과징금·형사처벌**.

**PivoxQuant 영향**:
- Weekly Memo / Brag Card / Earnings Pre-Brief 모든 Artifact = AI 생성물
- → **"AI 생성" 라벨 명시 의무**
- 기존 disclaimer ("AI 분석") 외에 **시각적 명확 라벨** 추가 필요

**변호사 자문 요청 포인트** (Q14):
- Artifact 템플릿 "AI 생성" 배지 적용 방식 (워터마크 vs 자막 vs 텍스트 라벨) 중 충족 형식
- PDF 헤더 + email subject + 웹 surface 일관 라벨 요건
- "AI 분석" 기존 표기로 충분한지 vs 명시적 "AI 생성" 필수인지

---

## 🟡 MEDIUM ④ — PIPA 매출 10% 과징금

| 항목 | 내용 |
|---|---|
| **공포** | 2026-03-10 (법률 제21445호) |
| **시행** | 2026-09-11 |
| **출처** | [boannews 실무 가이드](https://m.boannews.com/html/detail.html?idx=124648) / [국가법령정보센터](https://www.law.go.kr/LSW/lsInfoP.do?lsId=011357&ancYnChk=0) / [PIPC 안내](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS074&mCode=C020010000&nttId=9145) |

**핵심**: 반복 위반 / 대규모 피해 시 **매출 10% 징벌적 과징금**.

**PivoxQuant 영향**:
- §28-8 국외이전 (Stripe / Anthropic / Railway / Vercel = US) 동의 고지 형식 점검
- 현재 privacy-ko.md 국외이전 고지 명시되어 있으나 시행령 확정 후 재검토 필요

**변호사 자문 요청 포인트** (Q6 연결):
- 회원가입 cross_border 동의 형식 PIPA §28-8 + GDPR cross-cite 요건 충족 여부
- 시행령 확정 후 privacy-ko.md 갱신 방향

---

## 🟡 MEDIUM ⑤ — 금융소비자보호법 6대 판매원칙 강화

| 항목 | 내용 |
|---|---|
| **시행** | 2026-01-02 (이미 시행) |
| **출처** | [국가법령정보센터](https://www.law.go.kr/LSW//lsSideInfoP.do?lsiSeq=277247&joNo=0017&joBrNo=00&docCls=jo&urlMode=lsScJoRltInfoR) |

**핵심**: 6대 판매원칙 (적합성 / 적정성 / 설명 / 불공정영업 / 부당권유 / 광고규제). 금융상품판매업자등 적용.

**PivoxQuant 영향**:
- ✅ 정보 제공만 + 금융상품 판매 안 함 → 직접 적용 외
- ⚠️ "광고규제" 관점에서 PivoxQuant 마케팅 카피 (가격 표시 / 효과 묘사) 점검 권장

**변호사 자문 요청 포인트**:
- 정보 제공 SaaS가 "금융상품판매업자등" 정의에서 명확히 제외되는지
- 마케팅 카피 "수익률 보장", "전문가 추천" 등 forbidden_terms 패턴 일치 충분성

---

## 🟡 MEDIUM ⑥ — 전자상거래법 가분적 디지털콘텐츠 청약철회

| 항목 | 내용 |
|---|---|
| **시행** | 2026-07-21 |
| **출처** | [국가법령정보센터](https://law.go.kr/LSW//lsLawLinkInfo.do?chrClsCd=010202&lsId=009318&lsJoLnkSeq=1000527255&print=print) |

**핵심**: 가분적 디지털콘텐츠 = 제공 개시되지 않은 부분은 **청약철회 가능**.

**PivoxQuant 영향**:
- Pro / Premium 월 구독 = "가분적 디지털콘텐츠"로 해석 가능
- → **월 중도 해지 시 미사용분 환불 의무** 가능성
- 현재 terms-ko.md 환불 정책 (§17 14일 청약철회 단서) 재검토 필요

**변호사 자문 요청 포인트** (Q15):
- Pro/Premium 월 구독이 "가분적 디지털콘텐츠"로 해석되는지
- 월 중도 해지 시 미사용분 환불 의무 발생하는지
- terms-ko.md §17 환불 정책 갱신 방향

---

## 🟢 LOW ⑦ — KRX 데이터 라이선스 (변동 없음)

| 항목 | 내용 |
|---|---|
| **출처** | [pykrx GitHub README](https://github.com/sharebook-kr/pykrx) |

**핵심**: pykrx README "데이터 저작권은 각 제공자에게 귀속, 상업적 이용 시 ToS 준수 필수".

**PivoxQuant 영향**:
- 메모리 룰 [공식 라이선스만] (2026-04-19 결정 + 2026-05-09 KOSPI 누락 BLOCKED 확정) 정책상 **pykrx/yfinance 사용 금지**
- **변동 없음**, 정책 유지

**액션**:
- KRX Data Marketplace 공식 라이선스 가격 재확인 — 매출 발생 후 별도 트랙 (출시 후)

---

## 변동 없음 영역

- **자본시장법 §101 본문**: 개정 없음 (시행령 변경예고 2026-03-18~04-07 있었으나 §101 면제 요건 직접 변경 아님)
- **신용정보법 §32 / §22의9 마이데이터**: read-only 단일 broker (KIS) 운영에 직접 영향 없음
- **유사투자자문업 신고 갱신 5년 주기**: PivoxQuant 미신고 → 해당 없음

---

## 다음 액션 (변호사 의견서 수령 후)

### 즉시 자율 fix 가능 (코드/UI)
- AI 생성물 라벨 배지 (Artifact 템플릿 상단) — regulatory ③
- `services/ai/service.py:238` rec_shares 구체성 완화 — 자본시장법 §101 ④
- dead `i18n/ko.ts:390,403` "Pro 무료 체험 시작" 제거 — 표시광고법

### CEO 권한 (변호사 검토 필요)
- terms-ko §11.5 Free 사용자 손해배상 한도 분리
- terms-ko §17 가분적 디지털콘텐츠 환불 정책 갱신 (regulatory ⑥)
- privacy-ko 시행령 확정 후 갱신 (regulatory ④, 2026-08)
- companion / ai-chat 양방향 채널 변호사 사인 강제 (regulatory ②)

### 재스캔 일정
- **2026-08-15**: PIPA 9월 시행 직전 + 정통망법 시행령 확정 시점 재스캔

---

## 관련 첨부 (본 디렉터리)
- `service-overview.md` — PivoxQuant 서비스 개요
- `section-101-exemption-decision.md` — §101 면제 트랙 결정문 (HIGH ② 직접 연관)
- `legal-questions-q1-q15.md` — Q6 / Q12 / Q13 / Q14 / Q15 상세
