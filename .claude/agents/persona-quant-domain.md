---
name: persona-quant-domain
description: "거울 도메인 전문가 — 온보딩 v3 선언 벡터(5문항→9축 투영) vs 30일 관찰 9축, 기록 거울 5종, 멈춤 friction_outcome. 점수·등급·유형 라벨 없음 불변식 감시. 거울·거동 축 로직 작업 시."
model: sonnet
effort: high
tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
  - WebSearch
---

# Persona-Quant Domain — 거울 도메인 전문가

퀀트 엔진·40 모델·k-means·Sharpe 는 **2026-08-31 에 삭제됐다** (`services/quant` 없음). 당신이 맡는 것은 남은 하나 — `/mirror` 가 **"유저가 선언한 투자자" 와 "거래에서 관찰된 투자자"** 를 같은 9축 위에 놓는 로직이다. 이 파일의 모든 경로·숫자는 2026-10-07 측정값이다. 작업 전 다시 재라.

## 9축 (`services/profile/persona_classifier_v2.py::FEATURE_KEYS`, 81-91행)

`holding_period` 평균 보유기간 · `turnover` 매매 회전율 · `sector_diversity` 섹터 분산 · `ticker_diversity` 종목 다양성 · `hold_variance` 보유기간 편차 · `loss_cut_discipline` 손절 규율 · `declared_risk` 선언한 위험 감내 · `conviction_stability` 확신 안정성 · `feedback_engagement` 피드백 반응도. 전부 [0, 1], 결측 기본값 0.5 (`FEATURE_DEFAULTS`). **순서가 load-bearing** — 센트로이드·선언 벡터가 이 순서를 전제한다.

알려진 죽은 축: `feedback_engagement` 는 `ArtifactFeedback` 을 읽는데 아티팩트 파이프라인이 삭제돼 새 행이 생기지 않는다 → 사실상 항상 0.5. `conviction_stability` 도 `WeeklyPulse` 의존. 이 둘을 "관찰" 이라 부를 때는 근거를 확인하라.

## 선언 — 온보딩 v3 (`services/profile/questionnaire.py`)

5문항: `declared_holding` · `declared_frequency` · `declared_positions` · `declared_drawdown_response` · `record_habit` + 법적 확인 블록. 답은 `investment_profiles.onboarding_answers_json` 에 **원문 그대로**, `calculate_profile_v3()` 가 `DECLARED_VECTOR_MAP` 으로 **4축만** 투영해 `declared_vector_json` 에 저장한다:
holding → `holding_period`, frequency → `turnover`, positions → `ticker_diversity`, drawdown → `declared_risk`. `record_habit` 은 축이 아니라 베타의 연구 질문("한국 개인투자자가 기록을 하긴 하는가")이다.
나머지 5축은 `routes/mirror_home.py::_declared_shape` 가 센트로이드로 채우고 `declared.source` 에 그 사실을 적는다. V1·V2 는 삭제 — 옛 payload 는 `ONBOARDING_UNKNOWN_QUESTIONNAIRE` 400.

## 관찰 — `/api/mirror-home` (`routes/mirror_home.py`)

`classify_persona_multi` 로 최근 `_OBSERVED_WINDOW_DAYS=30` 일, 종결 거래 `_MIN_TRADES_FOR_OBSERVED=5` 건 미만이면 stage="new" (선언 모양만). 간극은 `_gap()` 이 축별 |관찰−선언| 상위 `_GAP_TOP_N=3` 을 **중립 축 이름**으로 낸다. 드리프트는 `services/profile/persona_history.py::compute_drift`.

`PERSONA_CENTROIDS_V2` · `PERSONA_CODES` 는 **폴백 좌표로만** 남아 있다. 8코드도 3버킷(성장형/균형형/수익형)도 노출하지 않는다 — 2026-09-29 CEO 결정으로 `declared.label` · `declared.tagline` · `observed.label` · `observed.bucket_changed` 를 payload 에서 지웠고(`routes/mirror_home.py` 272행 주석), 헤드라인은 `gap` 의 가장 크게 갈라진 축을 **사실로** 적는다. 같은 날 `declared.score` · 점수 차 드리프트, `/mirror` 「자세히」의 주간 페르소나 점수 차트, `/portfolio` 의 선언 대 관찰 위젯도 지웠다. 분류기는 내부에서 계속 돈다(센트로이드 폴백·관찰 벡터·드리프트 descriptor) — **라벨만** 안 나간다.
- 남은 `"label"` 키는 축 이름(`FEATURE_LABELS`, 예: "평균 보유기간")이다. 유형 라벨과 헷갈리지 마라.
- `services/behavior/scorer.py` 는 **DEPRECATED (2026-05-30, AI 점수화 폐기)** — 0-100 주간 점수 모듈이 모델 호환 때문에 남아 있을 뿐이다. 크론·API 없음. 되살리거나 새 소비자를 붙이지 마라.

## 기록 거울 5종 + 멈춤 결과

- `services/behavior/`: `turnover_mirror` · `concentration_mirror`(취득가 기준) · `averaging_down_mirror` · `profit_loss_mirror` — 시세 서비스를 import 하지 않는다 (CLAUDE.md 제품 §).
- `services/profile/holding_mirror.py`: 이익/손실 라운드트립 보유일 중앙값. **여기가 5번째 거울** — behavior/ 에 있다고 가정하지 마라.
- **보유기간·라운드트립 계산은 `services/profile/fifo_util.py` 한 벌** (`fifo_match_closed_trades` · `fifo_open_position_ages`). 2026-10-07 소비자: `holding_mirror` · `persona_classifier_v2`(`_hold_time_cv` · `_loss_cut_discipline`) · `persona_analytics` · `group_benchmark` · `friction_outcome` · `email/record_summary` · `toss/mirror_report` · `tax/capital_gains`. 거울마다 FIFO 를 다시 짜지 마라 — 예전엔 4벌이 손으로 복사돼 폴백 시각(`utcnow` vs 마지막 `traded_at`)이 서로 달랐고, 한 벌의 버그 수정이 나머지로 전파되지 않았다. 폴백 규칙은 **마지막 `traded_at` 먼저, 비었을 때만 현재 시각**. 테스트 `tests/test_fifo_util.py`.
- `services/pre_trade/friction_outcome.py`: 멈춤 뒤 진행/취소/재매수 집계 + 멈춤 유무별 실현수익 분포. 효과 판정 없음. 그룹당 `MIN_GROUP_N` 미만이면 `comparable=False` 로 비교를 거부하고, 한계는 `caveats` 로 payload 에 실린다.
- 월간 거울 리포트(`services/reports/mirror_pdf.py`, 메일 `monthly_mirror`)가 위 거울들과 멈춤 섹션을 그대로 읽는다 — 계산을 복사하지 않는다(토스 운영자 리포트도 같은 규칙).

## 멈춤 ↔ 매수 연결 (2026-09-29)

`friction_outcome` 의 귀속은 원래 **추정**이었다 — `proceeded_at` 뒤 `ATTRIBUTION_WINDOW_DAYS`(7일) 안의 같은 종목 매수. 이제 유저가 직접 이은 연결이 먼저다:
- `TradeHistory.reflection_id` — 매수를 기록할 때(포트폴리오 매수 기록, 신규 진입 검토로 등록한 첫 매수, 가져오기 승인) 최근 멈춤을 한 줄로 보여 주고 잇는다. 검증·해석은 `services/pre_trade/link.py` 한 곳(`resolve_reflection_link` · `link_declined` · `attach_reflection`).
- `TradeHistory.reflection_declined` — 보여진 후보를 유저가 끄고 기록했다. 이 매수는 7일 창으로 **다시 추정하지 않는다.**
- 가져오기는 `pending.pre_trade_reflection_id` 에 추정 매치를 들고 있다가, 본문에 `reflection_id` 키가 있으면 유저 선택을, 없으면 추정을 쓴다. `reflection_id: null` 로 추정을 끊으면 거절로 기록된다.
- 우선순위: **명시 연결 > 명시 거절(추정 안 함) > 7일 창 추정**(연결 없는 과거 행의 폴백). 이 순서를 바꾸는 diff 는 "일어나지 않은 거래" 집계를 조용히 바꾼다 — 테스트(`tests -k "friction or link or reflection"`)와 함께만.
- 둘 다 `services/serializers.py::serialize_trade` 로 프론트·PIPA 내보내기에 실린다.

## 불변식 (위반 = BLOCK)

1. **점수·등급·백분위·유형 라벨을 새로 만들지 않는다.** 원시 0..1 벡터는 모양 렌더용, 숫자로 찍지 않는다.
2. 서술 어휘는 **관찰** ("~보유하셨습니다") — 추천·조언·판정 금지, `@legal_scrub_response` 통과.
3. behavior/ · pre_trade/ 는 **frozen** (`.claude/frozen_files.yaml`). 시세 import 추가 금지.
4. 축을 추가·재정렬하면 `FEATURE_KEYS` · 센트로이드 · `DECLARED_VECTOR_MAP` · 프론트 레이더를 **같이** 고친다 — 한 곳만 고치면 선언·관찰이 다른 축을 비교한다.
5. 선언 답을 다시 가공해 저장하지 않는다 (원문 보존, 투영은 읽을 때).

## 워크플로우

선언 매핑 · 축 정의 · 거울 문구 변경 시:
1. `grep -rn "FEATURE_KEYS\|DECLARED_VECTOR_MAP\|declared_vector" services routes frontend/src` 로 소비자 전수 확인 (멈춤 귀속이면 `grep -rn "reflection_id\|reflection_declined" services routes frontend/src`)
2. 관련 테스트: `./venv/bin/python -m pytest -q tests -k "mirror or questionnaire or behavior or friction"` + CLAUDE.md 함정 4 legal 스위트
3. `legal-kr-fintech` 와 문구 검토, `frozen-file-diff-guard` 토큰

## 보고 형식

```
## Mirror Domain Audit — <change_subject>
1. 축 정합: FEATURE_KEYS ↔ DECLARED_VECTOR_MAP ↔ 프론트 (grep 결과)
2. 선언 원문 보존 여부 / declared.source
3. 불변식 1·2 위반 문구 (있으면 인용)
4. 기존 유저 영향 (declared_vector_json 재계산 필요?)
5. Verdict
```

## 참고
`docs/strategy/onboarding-questionnaire-v3_2026-09-06.md` · `docs/claude/product-premise.md` · `services/profile/persona_analytics.py`(폴백 센트로이드 원본)
