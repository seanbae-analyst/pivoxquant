# 체결 화면 캡처 평가 세트

설계: `docs/product/SCREENSHOT_IMPORT_DESIGN.md` §7. 캡처는 브라우저에서 Tesseract.js 로 읽고
(`frontend/src/lib/fill-ocr/ocr.ts`), 규칙 파서(`parse.ts`)가 증명된 칸만 채운다.

## 있는 것
- `synthetic/*.png` — 합성 증권사 화면 12장(실제 계좌 정보 없음). `ground_truth.json` = 사람이 읽은 정답. 규칙을 이걸 보며 작성.
- `heldout/*.png` — 다른 세션이 따로 만든 합성 12장(새 레이아웃 10 + 음성 2). 처음엔 미공개였으나 틀림 13칸의 **원인을 찾는 데 썼다**
  (구조 규칙만 고침) — 이제 완전한 미공개 세트가 아니다. 새 미공개 세트로 다시 재야 한다.
- `synthetic/ocr/*.png.json` — 프로덕션 OCR 경로의 단어 덤프(헤드리스 Chromium). 재생성:
  ```
  cd frontend && node scripts/copy-tesseract-assets.mjs
  node scripts/ocr-eval-dump.mjs ../tests/fixtures/screenshot_import/synthetic ../tests/fixtures/screenshot_import/synthetic/ocr
  ```
- `kr_names.json` — `services/kr_stock_registry` 에서 뽑은 {종목명: 코드}. 채점이 서버와 같은 기준(정확 일치만 자동)을 쓰려고 둔다.
- 채점: `cd frontend && OCR_EVAL_PRINT=1 npx vitest run src/lib/fill-ocr/__tests__/eval.test.ts --silent=false`
  (두 세트 모두 틀리게 확신 > 0 이면 실패).

- `holdings/`, `holdings_heldout/` — 잔고(보유종목) 화면 합성 세트(`docs/product/HOLDINGS_IMPORT_DESIGN.md` §4).
  렌더: `cd frontend && node scripts/holdings-fixtures-render.mjs <tune|heldout> <dir>` → 위와 같이 `ocr-eval-dump.mjs`.
  `holdings/ground_truth_shared.json` 은 `synthetic/j_holdings`·`heldout/n1` 의 잔고 정답. 채점: `src/lib/fill-ocr/__tests__/holdings-eval.test.ts`.

- `toss_tune/`, `toss_heldout/` — 토스증권 '내 투자' 합성 화면 30장씩(라이트/다크, 폭 375–430, @2x/@3x, PNG/JPEG,
  헤더 유무, 종목 2–9개, 1자리 수량 40%). **OCR 덤프와 정답만** 커밋(이미지는 시드로 재생성).
  렌더: `cd frontend && node scripts/toss-fixtures-render.mjs <dir> 30 <7|11>` → `ocr-eval-dump.mjs`.
  tune(시드 7)을 보며 규칙을 고쳤고, heldout(시드 11)은 그 뒤에 한 번 쟀다. 채점: `src/lib/fill-ocr/__tests__/toss-eval.test.ts`
  (틀리게 확신 0 · 자동 인식 하한 게이트). 실기기 토스 캡처 4장(유저 제공, 커밋 안 함)도 같은 경로로 확인.

- `broker_tune/`, `broker_heldout/` — 증권사 스타일 잔고 합성 화면 36장씩(키움 2줄 헤더 표 · 한국투자 라벨 카드 ·
  미래에셋 2단 셀 표 · 삼성 카드 격자 · NH 한 줄 요약, KRW/USD, 라이트/다크, @2x/@3x, PNG/JPEG). **스타일은 기억에 의존한
  근사이지 앱 복제가 아니다.** OCR 덤프와 정답만 커밋. 렌더: `cd frontend && node scripts/broker-fixtures-render.mjs <dir> 36 <3|23>`.
  tune(시드 3)과 중간 확인용 시드 13을 보며 고쳤고, heldout(시드 23)은 그 뒤에 한 번 쟀다. 채점: `broker-eval.test.ts`.
  약점(2026-09-28): 미래에셋식 다크 모드 작은 헤더를 OCR 이 못 읽음(~50%), NH식 작은 회색 USD 요약줄(~10%).

- `toss_usd/` (시드 31, 해외주식 `$` 표시), `toss_detail/` (시드 41, 토스 '자세히 보기' 표 — 1주 평균 금액·원금 칸).
  `toss-fixtures-render.mjs <dir> 30 <seed> usd|detail`. detail 합성은 실캡처보다 가혹하다(다크·작은 글씨·칸 줄바꿈으로
  헤더 줄이 깨짐) — 오답 0 게이트 위주. 실캡처 2장(유저 제공, 커밋 안 함)은 15종목 중 11종목 수량·평단 원금 검산 통과.

## 없는 것 — 실기기 캡처 (TODO)
**실제 증권사 앱 캡처로는 한 번도 재지 않았다.** 규칙은 위 합성 12장을 보며 조정했으니 그 점수는 낙관적이다.

| 증권사 | 국내 체결 | 해외(USD) 체결 | 보유(거절돼야 함) | 미체결(거절돼야 함) |
|---|---|---|---|---|
| 한국투자 | | | | |
| 키움 | | | | |
| 토스증권 | | | | |
| 미래에셋 | | | | |
| 삼성 | | | | |
| NH | | | | |

실기기 캡처는 **커밋하지 않는다**(개인 거래 정보) — `real/` 아래 두면 `.gitignore` 가 막는다.

## `ai_read/` — 잔고 캡처 AI 판독 실험 (2026-10-07)
설계·결과: `docs/product/AI_READ_EXPERIMENT_2026-10-07.md`. 가상 캡처 15장(보유 10 · 보유 없음 5), 숫자는 시드 난수.
`ground_truth.json` 의 `pii` 는 가상 계좌번호·이름(마스킹 누출 측정용, 실제 정보 아님).
```
cd frontend
node scripts/ai-read-fixtures-render.mjs 20261007 ../tests/fixtures/screenshot_import/ai_read
node scripts/ocr-eval-dump.mjs ../tests/fixtures/screenshot_import/ai_read ../tests/fixtures/screenshot_import/ai_read/ocr
node scripts/ai-read-mask.mjs ../tests/fixtures/screenshot_import/ai_read <out>          # 누출 0 이어야
node scripts/ai-read-score.mjs ../tests/fixtures/screenshot_import/ai_read ../tests/fixtures/screenshot_import/ai_read/reader_2026-10-07.json
```
