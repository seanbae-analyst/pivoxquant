# 데이터 신뢰성 전략 (Data Trust Strategy)

> **상태: 🟡 초안 / 미확정 (DRAFT — recorded, not committed)**
> 작성: 2026-05-31 · CEO 지시 "일단 기록만" 으로 파킹.
> 아직 DECISIONS.md(확정 결정 SoT)에 반영하지 않음 — 방향 확정 시 승격할 것.
> 기반: v55 재포지셔닝(2026-05-30 "거울/사전개입") + 외부 실측 검색(하단 Sources).

---

## 0. 핵심 프레임 — "신뢰 증명"은 사실 두 개의 다른 문제

CEO 질문("Oracle 같은 걸로 데이터 검증해서 신뢰 증명")엔 함정이 있다.
데이터 정확성과 감정데이터 willingness는 **다른 문제**이고, 섞으면 노력의 절반을
엉뚱한 데 쓴다.

| | **A. 데이터가 진짜인가** | **B. 사람이 자기 감정을 쏟아도 되는가** |
|---|---|---|
| 신뢰 대상 | 시장/퀀트 숫자 (가격·시그널·백테스트) | 내 감정·직감·매매이유 데이터 |
| 신뢰의 정체 | **기관 신뢰성** (institutional credibility) | **심리적 안전** (psychological safety) |
| 증명 수단 | 출처·타임스탬프·재현성·제3자 검증 ← **여기가 "Oracle"** | 비판단·암호화·통제권·정직함 |
| 현 상태 | **이미 ~80% 구현됨** | **거의 안 돼 있음 (진짜 과제)** |

**핵심 통찰:** "Oracle류 데이터 검증"은 **A를 강화**한다. 그런데 CEO가 원하는 것
("사람들이 세세하게 감정데이터를 다 넣게")은 **B의 문제**이고, 데이터 검증으론
거의 안 움직인다. 사람이 직감을 앱에 쏟는 이유는 "이 회사 데이터가 정확해서"가
아니라 **"여기선 안 판단받고, 내 거고, 안 새니까"** 다. Oracle을 붙여도 B는 그대로.

→ 전략 분기: **A는 "증명을 가시화"(이미 됨, 마감만), B는 새로 설계.**

---

## 1. "Oracle 협업 가능?" — 직답

"Oracle" 3가지 해석, 각각 판단:

| 해석 | 현실성 | 판단 |
|---|---|---|
| **Oracle社 / 블록체인 오라클(Chainlink류)** | 1인 pre-launch엔 과잉. 블록체인 오라클은 *온체인 자산용*, "내 PDF 리포트 신뢰"용 아님 | ❌ 하지 말 것 |
| **진짜 필요한 "oracle" = Trusted Timestamping / 데이터 어테스테이션** (RFC 3161, ANSI X9.95) | 데이터가 "시점 T에 존재, 이후 변조 없음"을 **제3자 누구에게나 증명**. 가벼운 SaaS·표준 | ✅ **정답** (중기) |
| **데이터 출처 자체가 이미 "oracle"** = FMP·Alpaca·KIS·SEC EDGAR·FRED 라이선스 | 이미 `services/artifacts/data_source_resolver.py` 로 *유저별 실제 출처만* 진실 표기 중 | ✅ **지금 가동 중** |

**진짜 협업 대상(Oracle 아님):**
1. **데이터 라이선서** — 이미 있음 (가시화만)
2. **보안 인증기관** — KISA → **ISMS-P** (한국 핀테크 신뢰 표준 앵커)
3. **학계** — 자본시장연구원 / 대학 행동재무 lab. 단 **효능 검증 아니라 "행동 사실 정확도" 검증**

---

## 2. Layer A — 데이터 무결성: 이미 강점, 마감만

**이미 구현됨 (실측 — 경쟁사보다 엄격):**
- `services/artifacts/data_source_resolver.py` — 하드코딩 출처 금지, 유저 실제
  broker 연결 + 공개 시스템 소스(FMP/SEC EDGAR/FRED)만 표기. 표시광고법 §3(허위표시)
  명시적 방어 (Wave 4 audit 2026-04-24 대응)
- `as_of` / `as_of_stamp` / `generated_at` 타임스탬프 (risk_board, self_audit,
  year_end_letter 등)
- `services/legal/` scrub + forbidden_terms + §101 detector

**갭 2개:**

| 갭 | 현재 | 목표 | 수단 |
|---|---|---|---|
| **자기주장 → 제3자 검증** | PDF가 "FMP, as-of X"라고 *말함*. 변조 안 됐다는 증거 없음 | "이 리포트는 시점 T 데이터로 생성, 사후 변조 0 — 누구나 검증 가능" | **trusted timestamping**: 리포트 hash를 RFC 3161 TSA에 등록. 17개 아티팩트 PDF에 검증 푸터 |
| **방법론 블랙박스** | 산출식이 코드 안에만 | 유저가 "이 숫자 어떻게 나왔나" 클릭→확인 | 공개 methodology 페이지 (GKYZ/HRP/4-pillar — *식은 공개, 가중치는 영업비밀 OK*) |

→ **재현가능성이 최강의 신뢰 증명.** "우리 숫자는 공개데이터로 당신이 직접
재계산 가능" = 블랙박스 아님 = AI 핀테크 불신 시대의 차별점.

---

## 3. Layer B — 감정/행동 데이터 신뢰: 진짜 과제 (새로 설계)

**"신뢰"는 3종류, 셋 다 v55 research와 정합해야 한다:**

**(a) 프라이버시 신뢰 — "내 감정데이터 안 새나"**
- 암호화 저장 + 광고/제3자 미제공 + 삭제권(PIPA §36)
- 경쟁사 핵심도 이것: TradesViz는 *"수집·이용을 유저가 언제든 허용/금지"* 통제권 전면화
- 기관 앵커: **ISMS-P** (2027.7 중요 개인정보처리자 의무화 예정, 2026 현장실증 심사
  강화 중). 지금 취득은 무겁지만 **"ISMS-P 지향 설계"를 로드맵에 박는 것** 자체가 신뢰 메시지

**(b) 비판단 신뢰 — "여기선 점수 안 매겨서 솔직해진다"**
- v55가 입증한 *유일하게 맞는 방향*. AI 점수화 폐기 = 법(PIPA §23 민감정보) + 심리 둘 다 정답
- 이미 `living_mirror_service.py` / `insider_mirror_service.py` /
  `pre_trade_checklist_service.py` 로 "거울/사전개입" 착수됨
- 카피: "**거울이지 심판이 아닙니다. 채점·추천 없음.**"

**(c) Confabulation 정직 — 신뢰의 역설적 무기**
- research: 사람은 매매 이유를 **43% 지어냄**(choice-blindness). "왜 샀어?" 기록 ≠ 진실
- 보통 앱은 숨기고 "당신의 진짜 이유를 분석"이라 거짓 정밀성을 판다
- **PivoxQuant는 반대로 인정**: *"당신이 적은 이유가 진짜가 아닐 수 있다는 걸 우리도
  압니다. 그래서 점수 안 매기고, 패턴만 보여줍니다."*
- → **정직한 한계 인정이 오히려 신뢰를 올린다.** (과잉약속 경쟁사와 정반대 포지션)

**Layer B 철칙:** 효능은 약속 금지, **행동 사실만 거울처럼** — 100% 증명 가능:
- "이번 달 47회 매매, 회전율 1,600%" (자본시장연구원 20만명 실측)
- "고회전 11.4% vs 저회전 18.5% = 연 7%p" (Barber & Odean N=66,465)
- → *우리 제품 효능*이 아니라 *학술 사실* → 표시광고법 안전

---

## 4. 신뢰를 "증명"하는 5단 피라미드 (로드맵)

| 단계 | 무엇 | 협업 필요? | 시점 | 비용 |
|---|---|---|---|---|
| 1 | 출처·면책·as-of 가시화 + 방법론 공개 | ✗ (코드) | **지금** | 0 |
| 2 | 프라이버시 정책 + 데이터 통제 UI + 비판단/confabulation 카피 | ✗ (코드) | **단기** | 0 |
| 3 | Trusted timestamping (아티팩트 변조방지 검증) | TSA SaaS | 중기 | 저 |
| 4 | **ISMS-P** 인증 (또는 ISMS 우선) | KISA/인증기관 | 중기(유료결제·스케일 후) | 고 |
| 5 | 학술 검증 — *효능 아닌 "행동 사실 정확도"* | 자본시장연구원/대학 | 중장기 | 중 |

**투명성 자체가 마케팅:** *"우리는 증명할 수 있는 것만 약속한다"* = 정직 포지셔닝의 핵심 차별점.

---

## 5. 절대 하지 말 것 (legal + research 게이트)

- 🟥 "감정 기록하면 수익 향상/투자 개선" 증명 시도 — 효능 미입증 → **표시광고법 위험 +
  v55 마케팅게이트 위반**
- 🟥 가짜 정밀성 — 감정점수 → 수익예측 매핑 (confabulation 무시)
- 🟥 인증 미취득 상태에서 "보안인증/검증완료" 배지 오용
- 🟥 블록체인 오라클로 "온체인 검증" 마케팅 (기술 미스매치, 신뢰 역효과)

---

## 6. 90초 요약

1. **두 신뢰를 분리하라.** 데이터 정확성(A)과 감정데이터 willingness(B)는 다른 문제. Oracle은 A만 도움.
2. **"Oracle 협업" 답: 안 함.** 우리 oracle은 이미 `data_source_resolver.py` 에 있고,
   다음은 *trusted timestamping*(표준, 가벼움)이지 Oracle社/블록체인 아님.
3. **Layer A는 80% 됨** — 가시화 + 재현성 + 타임스탬프 마감만.
4. **Layer B(진짜 과제)의 신뢰 레버는 데이터검증이 아니라 심리적 안전** — 비판단 +
   프라이버시 + "당신 이유가 진실이 아닐 수 있음을 인정"하는 정직함.
5. **효능은 증명 대상이 아니라 경험으로 제공.** 증명하는 건 *행동 사실*(과잉거래 비용)뿐.

---

## Sources (2026-05-31 실측)

- Tradervue — https://www.tradervue.com/
- TradesViz Privacy — https://www.tradesviz.com/privacy/
- ISMS-P 2026 개편(이글루) — https://www.igloo.co.kr/security-information/보안-101-2026-isms-p-대개편-ceo가-반드시-챙겨야-할-3가지-변화/
- 핀다 ISMS 사례 — https://www.venturesquare.net/1065801
- Trusted Timestamping(Wikipedia) — https://en.wikipedia.org/wiki/Trusted_timestamping
- Blockchain Timestamping 2025(OriginStamp) — https://originstamp.com/blog/reader/blockchain-timestamping-2025-data-integrity/en
- 행동재무 2025(AJEAF) — https://ajeaf.com/index.php/Journal/article/download/73/85/140

## 구현 진행 상황

### ✅ Stage 1 — 방법론 투명성 (methodology transparency) — 2026-05-31 빌드 · 2026-06-01 legal 게이트
재현성 = 최강의 신뢰 증명. 흩어진 모델 공개를 통합 트러스트 surface로.
- **백엔드** `GET /api/methodology` (observation-only, **flag-gated** — 기본 로그인 필요, `METHODOLOGY_PUBLIC=1` 로 public 전환):
  - `routes/methodology.py` — 40모델(39 active) 카탈로그 + 각 모델 `academic_source`
    + 시스템 데이터 lineage(FMP/SEC EDGAR/FRED) + 재현성 선언 + disclaimer
  - `services/artifacts/data_source_resolver.py::system_data_lineage()` — 출처를
    프론트 하드코딩 않고 서버에서 진실하게 제공 (표시광고법 §3 방어 일관)
  - `routes/__init__.py` 블루프린트 등록
- **프론트** `/methodology` 대시보드 페이지:
  - `frontend/src/app/(dashboard)/methodology/page.tsx` (v3 editorial 프리미티브, raw hex 0)
  - `endpoints.ts` / `types.ts` / `hooks.ts(useMethodology)` / `layout.tsx`(disclaimer 매핑)
- **검증**: live test-client 200 · BANNED HITS 0 · tsc 0 error · ESLint clean ·
  `tests/test_methodology.py` 6 passed · test_quant_composer 100 passed (무회귀)
- **잔여**: 브라우저 success-path 렌더 스크린샷(로컬 스택+OAuth 게이트 의존) — 미실행
- **2026-06-01 legal-kr-fintech 검수 → FLAG-GATED 조치**: academic_source public
  공개가 §101/영업비밀에 "LIKELY SAFE"이나 Q-DT4 미해결 → 보수 원칙(불확실=막는
  쪽)으로 `METHODOLOGY_PUBLIC` 플래그 뒤 로그인 게이트(기본 OFF). 베타기간
  무비용(Vercel 게이트 하위). Q-DT4 변호사 사인 후 플래그 ON = public 복원.
  test 8개(6 schema + 2 gate) · 거짓 "No auth" 프론트 주석 정합.

### ⏳ 다음 (CEO 지시 대기)
- Stage 1 잔여: per-metric `methodology` 문자열(risk_quant 등) 페이지 통합 / 공개 라우트화
- Stage 2: 데이터 통제 UI(기능부) + **비판단/confabulation 카피(legal-kr-fintech 검수 후)**
- (다) `legal-kr-fintech` 로 timestamping/ISMS-P/학술검증 한국 법적 표기 한계 정밀 검수
- 방향 확정 시 → DECISIONS.md 승격
