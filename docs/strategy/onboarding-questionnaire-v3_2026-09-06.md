# 온보딩 문항 v3 제안 — "선언은 거울에 되비칠 수 있는 것만 묻는다"

> 작성: 2026-09-06 · 대상: 배상현(CEO)
> 선행 진단: 같은 날 세션 — 19문항 중 실제 소비되는 신호는 `profile_type` 하나와
> `risk_tolerance`(1~10) 하나뿐. 재산·월투자액·수입안정성 3문항은 소비처 0곳.
>
> **✅ 구현 완료 (2026-09-06, 같은 날).** 경쟁 조사
> (`onboarding-competitor-research_2026-09-06.md` §6) 반영으로 §3의 7문항 중
> Q4(내려가면)·Q5(오르면)를 뺀 **5문항 + 법적 확인**으로 확정. 빠진 둘은 pre-trade
> 7문항의 손절선·목표 문항이 이미 매매 직전에 같은 것을 묻는다.
> 구현 실측:
> - 백엔드 `services/profile/questionnaire.py::QUESTIONNAIRE_V3` ·
>   `calculate_profile_v3` (규칙표 → 8코드, 선언 벡터, 원답변 statements)
> - `investment_profiles` 컬럼 3개 추가 (`questionnaire_version` ·
>   `onboarding_answers_json` · `declared_vector_json`) — alembic `050` + `app.py` 부팅 self-heal
> - `POST /api/profile/onboarding` · `PUT /api/profile` 는 v3 payload 와 빈 skip 만 받는다. **V1·V2 코드 삭제** (`calculate_profile_type`, `QUESTIONNAIRE_V2`, `PROFILE_PRESETS_V2`, `INVESTOR_TYPES`, 테스트 2파일). `GET /api/profile/questionnaire` 는 v3 만 서빙
> - `routes/mirror_home.py` — 선언 벡터가 있으면 유저 답을, 없으면 센트로이드. 간극은 **선언한 축에서만** 계산. 응답에 `declared.source` (`self`/`centroid`) · `radar.declared_axes`
> - 프론트 `onboarding-questions.ts` v3 · 결과 화면은 유형 라벨 없이 답변 문장 그대로 · 프론트 복제 분류기 `classifyInvestorTypeLocal` 삭제 (−110줄)
> - V2 법적 확인 문구의 "AI-generated analysis" 정정 (R0 잔여)
> - 테스트: `tests/test_questionnaire_v3.py` 22건 신규 · pytest **1995 passed / 0 failed** (V2 테스트 29건 삭제 후) · vitest **368 / 368** · tsc · lint · next build 통과 · URL rule 121 / blueprint 23 (변경 전과 동일)
> - Playwright 헤드리스 E2E (dev-login → 5문항 → 법적 확인 → 저장 → 결과 화면 → `/mirror`): 통과. `/api/mirror-home` 응답 `declared.source == "self"`, `declared_axes` 4개, 콘솔 에러 0

---

## 0. 한 줄 결론

**19문항 → 7문항 + 법적 확인 1블록.** 문항 하나하나가 관찰 페르소나 9축
(`persona_classifier_v2.FEATURE_KEYS`) 또는 behavior mirror 5종 중 하나에 **1:1로
대응**한다. 대응 없는 문항은 넣지 않는다. 그래야 `/mirror`가 "당신이 말한 것"과
"당신이 한 것"을 같은 자로 잰다.

---

## 1. 지금 구조의 근본 문제 (실측)

### 1.1 거울이 유저의 말을 안 본다

`routes/mirror_home.py:59` `_declared_centroid(code)` 는 유저 답변이 아니라
**유형 라벨의 센트로이드**(`PERSONA_CENTROIDS_V2[code]`)를 "선언"으로 쓴다.
즉 지금 간극은 *"value_hunter 라벨을 받은 사람의 평균적 모습"* 과 관찰치의 차이지,
*이 유저가 말한 것*과의 차이가 아니다. 19문항을 답해도 유저 말은 8개 라벨 중
하나로 압축된 뒤 버려진다 (원답변 미저장 — `routes/profile.py:369~` 실측).

### 1.2 문항이 삭제된 제품용이다

"AI가 매일 관리", "레버리지 최대", "PivoxQuant을 계속 쓰기 위한 최소 연간 수익률",
`maps_to: tp_min / sl_max / scan_interval` — 전부 2026-08-31 삭제된 퀀트 엔진의
파라미터다. `apply_preset()` 이 쓰는 12개 컬럼의 읽는 코드는 0곳.

### 1.3 프론트/백엔드 문구가 이미 갈라졌다

법적 확인 5번째 항목: 프론트(`onboarding-questions.ts`, ba6dfe48 이후)는
*"직접 입력한 기록을 되비추어 보여줄 뿐"* 으로 정정됐지만 백엔드
`services/profile/questionnaire.py:411` 은 아직 *"AI-generated analysis"* 다.
`GET /api/profile/questionnaire` 가 이 백엔드 문구를 그대로 내보낸다.

---

## 2. 설계 원칙

1. **관찰 대응 원칙** — 나중에 거래 기록으로 검증할 수 없는 선언은 묻지 않는다.
2. **판정 없음** — 모든 문항은 "나는 보통 ~한다"의 서술이지 좋고 나쁨이 없다
   (DECISIONS: AI 점수화 폐기 · research_cbt_bias_model: 사실만 비추고 재구성은 사용자).
3. **PIPA 최소수집** — 재산 규모·소득 등 목적 없는 민감 정보 수집 중단.
4. **30초** — research_habit_premise: 체크인 30초 초과 시 D30 완주율 하락. 7문항 × 탭 1회.
5. **베타의 연구 질문을 문항에 싣는다** — CLAUDE.md §제품 전제: *"한국 개인투자자가
   기록을 하긴 하는가"* 는 조사로 못 푼다. 온보딩에서 직접 묻는다 (Q7).

---

## 3. 제안 문항 (7 + 법적 1)

각 문항의 **관찰 축** 열이 이 문항이 존재하는 유일한 이유다.

| # | 문항 (KR) | 선택지 | 관찰 축 (검증 방법) |
|---|---|---|---|
| Q1 | 한 종목을 사면 보통 얼마나 들고 있나요? | 하루 안 / 며칠 / 몇 주 / 몇 달 / 1년 이상 | **D1 holding_period** — FIFO 평균 보유일, log-norm 1~180일 |
| Q2 | 한 달에 매수·매도를 대략 몇 번 하나요? | 0~2 / 3~5 / 6~15 / 16~40 / 40+ | **D2 turnover** — 30일 체결 건수/일 · turnover mirror |
| Q3 | 보통 몇 종목을 동시에 들고 있나요? | 1~3 / 4~8 / 9~15 / 16~25 / 25+ | **D4 ticker_diversity** — 고유 티커 수 log-norm vs 25 · concentration mirror(최대 종목 비중) |
| Q4 | 산 종목이 내려가면 보통 어떻게 하나요? | 정한 선에서 판다 / 상황 봐서 판다 / 그냥 둔다 / 더 산다 | **D6 loss_cut_discipline** (손실 매도 보유일 / 이익 매도 보유일) · averaging_down mirror (평단 아래 추가매수 건수) · profit_loss mirror |
| Q5 | 오른 종목은 보통 어떻게 하나요? | 목표에 오면 판다 / 조금 오르면 판다 / 계속 든다 / 더 산다 | **D6 / profit_loss mirror** 이익 측 — Q4와 쌍으로 처분효과 양쪽을 선언 |
| Q6 | 포트폴리오가 한 주에 10% 빠졌다고 상상해 보세요. 실제로 무엇을 하나요? | 다 판다 / 일부 판다 / 둔다 / 조금 더 산다 / 크게 더 산다 | **D7 declared_risk** — `risk_tolerance` 1~10 로 저장 (현행 컬럼 유지, 분류기 D7 입력) |
| Q7 | 지금까지 매매 이유를 어딘가에 적어 본 적 있나요? | 없다 / 가끔 메모 / 노트·앱에 꾸준히 / 예전엔 했다 | **관찰 축 아님 — 베타의 연구 질문.** 이후 pre-trade 기록률과 교차하면 "기록한다고 말한 사람이 실제로 기록하는가"가 나온다 |
| L | 법적 확인 (현행 5항목, 프론트 정정본 기준) | 체크 5개 | `legal_confirmed` 게이트 유지 |

### 문항별 선택지 → 관찰 축 정규값 (선언 벡터)

거울이 유저 말과 직접 비교하려면 선언을 [0,1] 로 놓아야 한다. 관찰 쪽 정규화와
**같은 눈금**을 쓴다.

| 문항 | 선택지 값 → 선언 정규값 | 근거 |
|---|---|---|
| Q1 | 하루 0.0 · 며칠 0.25 · 몇 주 0.60 · 몇 달 0.85 · 1년+ 1.0 | `_norm_log(days, floor=1, ceil=180)` 실측: 3일 0.21 · 21일 0.59 · 90일 0.87 · 365일 1.0 |
| Q2 | 0~2회 0.05 · 3~5 0.45 · 6~15 0.70 · 16~40 0.92 · 40+ 1.0 | `_norm_log(per_day, floor=0.02, ceil=1.0)` 실측(월 건수/30): 1회 0.13 · 3회 0.41 · 15회 0.82 · 40회 1.0 |
| Q3 | 1~3 0.20 · 4~8 0.55 · 9~15 0.75 · 16~25 0.90 · 25+ 1.0 | `_norm_log(n, floor=1, ceil=25)` 실측: 2 → 0.22 · 6 → 0.56 · 12 → 0.77 · 20 → 0.93 |

(위 실측은 2026-09-06 `./venv/bin/python` 으로 `persona_analytics._norm_log` 를 직접 호출한 값.)
| Q4 | 정한 선 0.85 · 상황 봐서 0.6 · 둔다 0.3 · 더 산다 0.1 | `_loss_cut_discipline`: 손실을 이익보다 빨리 자르면 0.75+ |
| Q6 | 다 판다 1 · 일부 3 · 둔다 6 · 조금 더 8 · 크게 더 10 → `(rt-1)/9` | 현행 C1 점수표 그대로 |

Q5·Q7 은 벡터에 넣지 않는다. Q5 는 profit_loss mirror 이익 측 문장과 짝지어
텍스트로만 되비추고, Q7 은 분석용 컬럼이다.

### 채우지 않는 축

- **D3 sector_diversity** — 유저는 자기 섹터 분산을 선언할 수 없다(대부분 모른다).
  `_sector_map_from_positions` 도 KR 만 부분 매핑. 선언 없음 = 0.5 중립 유지.
- **D5 hold_variance** — "보유기간이 들쭉날쭉한가"는 자기 인식이 거의 없다. 중립.
- **D8 conviction_stability** — WeeklyPulse 에서만. 온보딩과 무관.
- **D9 feedback_engagement** — 가중치 0 (dormant). 무관.

---

## 4. 선언 페르소나 결정 규칙 (8코드 유지, 노출은 3버킷)

`profile_type` 컬럼과 `DECLARED_TO_PERSONA` · `group_benchmark` 가 8코드에 의존하므로
코드는 유지한다. 단 센트로이드 거리 대신 **Q1·Q2·Q6 3개로 결정하는 규칙표**로 바꾼다
— 사람이 읽을 수 있고, 유저에게 "왜 이 유형인가"를 문장으로 보여줄 수 있다.

```
Q1 하루 안               → daytrader
Q1 며칠 & Q2 16+         → speculator
Q1 며칠/몇 주            → growth
Q1 몇 달 & Q6 ≤ 3(판다)  → income
Q1 몇 달                 → balanced
Q1 1년+ & Q6 ≥ 8(더 산다) → value
Q1 1년+                  → income
Q7 없다 & Q1 몇 달 이상   → beginner  (선택: 기록 경험 0 + 장기 = 초심자 버킷)
```

노출은 현행 `PERSONA_TO_SURFACE` 3버킷(성장형/균형형/수익형) 그대로. `quant` 코드는
선언으로는 못 나온다 — 관찰(D6·D4 높음)에서만 나오게 두는 게 맞다.

`risk_tolerance` = Q6 점수(1~10). `time_horizon` = Q1 (하루·며칠·몇 주→short, 몇 달→medium,
1년+→long). 나머지 컬럼(`investment_goal`·`daily_time`·`auto_trade_preference`·프리셋 12개)은
쓰기 중단 후보 — 읽는 코드가 없다.

---

## 5. 거울에 미치는 변화 (이 제안의 진짜 목적)

**Before** — `/mirror` 간극 = `PERSONA_CENTROIDS_V2[선언코드]` vs 관찰 벡터.
유저가 무엇을 답했든 같은 코드면 같은 "선언".

**After** — 간극 = **유저 본인의 선언 벡터** (Q1·Q2·Q3·Q4·Q6, 나머지 0.5) vs 관찰 벡터.
표시 문장이 이렇게 바뀔 수 있다:

> 처음에 "몇 달 들고 있다"고 적으셨습니다. 지난 30일 실제 평균 보유는 9일이었습니다.

이건 판정이 아니라 두 사실의 병치다 — 현행 mirror 문체 그대로 간다.

구현상 필요한 것: 선언 벡터를 저장할 곳 하나 (`investment_profiles.declared_vector_json`
TEXT 1컬럼, 또는 원답변 JSON 1컬럼에서 매번 계산). 원답변 보존은 지금 없는 기능이고
Q7 분석에도 필요하다.

---

## 6. 빠지는 12문항과 이유

| 빠지는 문항 | 이유 |
|---|---|
| 투자 경력, 거래해 본 자산 | experience 축은 관찰 불가. 분류 가중치 1.0 이었으나 검증 수단 없음 |
| 재산 규모, 월 투자 가능액, 수입 안정성 | 소비처 0. 민감정보. PIPA 최소수집 |
| 리밸런싱 주기 | "AI가 매일 관리" 옵션 — 삭제된 제품. 관찰 축 없음 |
| 레버리지 | 관찰 불가(KIS read-only 는 신용 여부 안 줌). 무료 관찰 도구에 부적절 |
| -40% 개별종목 / -30% 시장 시나리오 | Q4·Q6 와 중복. 3개 시나리오 평균이 1개보다 정확하다는 근거 없음 |
| 기대 수익률, 수익 vs 안정, 최소 수익률 | 수익을 암시하는 문항. 제품이 수익을 약속하지 않는데 "계속 쓰기 위한 최소 수익률"을 묻는 것은 §101 경계에서 불필요한 노출 |
| 아는 개념, 리포트 자신감 | `knowledge_score`·`ui_complexity` 소비처 0 |

---

## 7. 실행 순서 (사인 떨어지면)

1. `services/profile/questionnaire.py` — `QUESTIONNAIRE_V3` + `calculate_profile_v3()`
   (규칙표 + 선언 벡터). V2 는 삭제하지 않고 남긴다 — 기존 행 `profile_type` 호환.
2. `routes/profile.py::submit_onboarding` — v3 키 감지 → v3 경로. 원답변 JSON 저장.
   법적 게이트 로직 그대로.
3. `frontend/src/data/onboarding-questions.ts` — 백엔드 정의를 **복제하지 말고**
   `GET /api/profile/questionnaire` 를 읽게 전환. `classifyInvestorTypeLocal` 삭제
   (두 번째 진실 원천 제거 — CLAUDE.md 함정 §10 과 같은 교훈).
4. `routes/mirror_home.py::_declared_centroid` → 선언 벡터가 있으면 그걸, 없으면
   센트로이드 (기존 유저 호환).
5. 테스트: `test_questionnaire_v2_wave_d1.py`(24) · `test_onboarding_sequence.py`(17) 를
   v3 로 복제, 특히 법적 게이트 400 케이스와 skip 경로 유지 확인.
6. 백엔드 `questionnaire.py:411` "AI-generated analysis" 문구는 **v3 와 무관하게 지금
   고쳐야 한다** (R0 잔여).

예상 규모: 백엔드 ~300줄 / 프론트 −400줄(복제 로직 삭제) / 마이그레이션 1 (TEXT 컬럼 1).

---

## 8. 열어 둔 결정 (CEO)

- **Q7 을 넣을지.** 관찰 축이 없는 유일한 문항. 대신 베타의 연구 질문에 직접
  답한다. 나는 넣는 쪽을 권한다 — 온보딩 외에 이 데이터를 얻을 자리가 없다.
- **8코드 유지 vs 3버킷으로 축소.** 유지를 권한다 — `group_benchmark` 와 관찰
  분류기가 8코드로 돌고, 노출은 이미 3버킷이라 유저 경험은 같다.
- **기존 온보딩 완료 유저 처리.** R0 절에 "노출 구간 가입자 0명"이라 적혀 있다.
  사실이면 재온보딩 강제 없이 v3 로 바로 갈 수 있다.
