# 잔고(보유종목) 화면 캡처 → 포지션 한 번에 — 설계

**작성일**: 2026-09-27 · 이웃 설계: [SCREENSHOT_IMPORT_DESIGN.md](SCREENSHOT_IMPORT_DESIGN.md) (원칙·OCR 엔진·CSP 동일)

## 1. 흐름
```
/portfolio [+ 기록] → AddPositionModalV2 → "잔고 캡처로 한 번에 가져오기"
  → 캡처 선택(여러 장) → [읽기]: 브라우저 Tesseract.js → lib/fill-ocr/parse-holdings.ts (증명된 칸만)
  → POST /api/portfolio/holdings-import/preview {rows:[{name, code, currency}]}   ← 숫자·이미지 없음, DB 쓰기 없음
  → 검토 표: 종목(TickerSearch) · 보유수량 · 평균단가 · 통화 · 지금 기록 · 처리(덮어쓰기 기본 / 더하기 / 건너뛰기)
  → 동의 체크 → POST .../commit {consent, rows:[{ticker, shares, avg_cost, currency, mode}]} → 토스트 요약 → 포트폴리오 새로고침
```
체결 화면은 이 패널에서 이름을 대고 거절하고, 체결 패널은 계속 잔고 화면을 거절한다.

## 2. 읽는 규칙 (`parse-holdings.ts`) — 칸은 화면이 증명할 때만

| 칸 | 채우는 조건 |
|---|---|
| 평균단가 | **라벨이 붙은 숫자만**(평균·평균단가·평단·매입가…, 표는 그 열 머리글 아래). 라벨 없는 숫자·현재가·평가금액은 절대 평균단가가 되지 않는다. 두 판독 일치 또는 교차검증 |
| 보유수량 | 뒤에 `주` 토큰, 또는 보유수량/잔고수량 라벨·열. `%`는 숫자 아님(`6%` = 6주 오독). 원화는 정수만 |
| 교차검증 | 수량×평균 ≈ 대상(±0.5%). 대상 = 매입금액, 또는 평가금액−평가손익, 또는 이름 줄의 라벨 없는 금액(매입/평가 둘 다 시도). 판독 조합이 정확히 하나면 채택 |
| 하드 게이트 | 대상이 보이는데 증명된 수량·평균이 어느 조합으로도 맞지 않으면 두 칸 비움(`amount_mismatch`) |
| 평균 유도 | 평균 열이 없고 수량·매입금액이 증명되면 매입금액÷수량, **나누어떨어질 때만**(원 단위/센트) |
| 섞인 레코드 | 한 레코드에 같은 라벨이 두 번 → 그 칸들 비움 |
| 종목·코드 | fills 와 같음: 6자리 코드는 이름 줄/이름 열에서만, US 티커는 `$` 금액 줄에서만. 확정은 서버 |
| 통화 | 행의 `$`/`원`, 없으면 화면 전체가 한쪽일 때만. 서버가 KRX 종목으로 확정하면 KRW 로 채움(원화로만 거래). US 종목은 절대 추정 안 함 |
| 행 누락 방지 | 수량 줄을 못 읽은 종목도 이름 줄이 있으면 빈 행으로 남긴다(조용히 빠지지 않게) |

## 3. 서버 (`routes/holdings_import.py`, `services/imports/holdings_import.py`, `services/position_writes.py`)
- preview: ocr_rows 와 같은 해석(KRX 마스터에 있는 코드만, 퍼지 → `needs_confirm`, 실패 → `needs_ticker`) + US 마스터 확인 + 유저의 기존 포지션.
- commit: 모든 행을 먼저 검증 — 하나라도 틀리면 400(`IMPORT_INVALID_FIELD` / `IMPORT_CURRENCY_MISMATCH` / `IMPORT_DUPLICATE_TICKER`, 행·필드 명시), 아무것도 안 씀. 동의 필수, 1~200행, KRW 수량 정수, 통화는 종목 통화와 같아야 함(조용히 바꾸지 않음).
- 한 트랜잭션. `replace` = 수량·평균단가만 캡처 값으로(thesis·매수일 등 유지), `add` = create_position 의 가중평균 병합(같은 코드), 기존 없음 = create_position 과 같은 insert.
- **FX**: insert·add 는 create_position 과 동일. replace 는 USD 행의 `buy_fx_rate` 를 캡처 시점 환율로 — 새 평균단가는 새 원가 기준이라 옛 환율과 섞지 않는다.
- **trade_history 안 씀**: 수동 포지션 생성·수정(POST/PUT/PATCH)도 쓰지 않는다 — 체결이 아니라 보유 기록이다.
- **무료 한도**: create_position 과 같은 유저 행 잠금 아래에서 새 종목을 요청 순서대로 한도까지, 나머지는 `skipped: TIER_LIMIT`(배치 실패 아님). 기존 종목 replace/add 는 한도와 무관.
- 동시 insert 경합 → 전체 롤백 409 `POSITION_RACE`. 응답 `{created, replaced, added, skipped}`, `legal_scrub_response`, 레이트리밋은 포지션 쓰기와 같음.

## 4. 정확도 (2026-09-27, 프로덕션 `ocr.ts` 경로 덤프 · `holdings-eval.test.ts`)
측정 단위는 종목 행의 칸. 종목은 서버 기준(코드는 마스터에 있을 때, 이름은 정확 일치만 — 퍼지는 판별불가로 셈).
**틀리게 확신 > 0 이면 테스트 실패.** 모든 체결·주문·기타 화면(3개 세트 22장, 해상도 거절 1장 제외)에서 잔고 행 0 도 게이트.

| 세트 | 칸 | 자동 인식 | 판별불가 | 틀리게 확신 | n |
|---|---|---|---|---|---|
| 조정용 8장(합성 6 + #594 의 `j_holdings`·`n1`) | 종목 / 수량 / 평균단가 / 통화 | 69% / 80% / 86% / 89% | 31% / 20% / 14% / 11% | **0** | 35행 |
| held-out 4장(규칙 작성 **후** 생성, 규칙 수정에 안 씀) | 종목 / 수량 / 평균단가 / 통화 | 38% / 56% / 69% / 75% | 63% / 44% / 31% / 25% | **0** | 16행 |

held-out `v04`(US 표)는 화면 판별에서 other(행 0) — 재현율 손실, 저장되는 것 없음.

## 5. 한계
- **실기기 캡처로 재지 않았다.** 모두 합성(HTML → 헤드리스 Chromium, `frontend/scripts/holdings-fixtures-render.mjs`). held-out 도 같은 렌더러라 레이아웃 다양성이 좁다.
- 표 머리글이 두 줄(평가금액/매입금액 겹침)인 화면, 평균단가를 원화 환산으로만 보여주는 US 화면은 미지원(통화 충돌로 막힘).
- 동의 문구는 기존 가져오기 동의(`journal.import.page.consentLabel`)를 그대로 쓴다 — "시각·원문 한 줄" 표현은 잔고 가져오기에 딱 맞지 않음(원문은 저장하지 않음). 문구 분리는 후속.
