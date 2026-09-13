# Import Inbox — 설계 (Phase 1: CSV/엑셀 + 스크린샷 텍스트)

**작성일**: 2026-09-13 · 전략: [launch/ACCOUNT_SYNC_STRATEGY_V2.md](../launch/ACCOUNT_SYNC_STRATEGY_V2.md) · 법적 근거: [launch/LOCAL_AGENT_LEGAL_RISK_2026-09-13.md](../launch/LOCAL_AGENT_LEGAL_RISK_2026-09-13.md)

## 원칙
1. **서버는 증권사 키·이미지·AI를 쓰지 않는다.** 받는 것은 유저가 올린 파일과 텍스트뿐. OCR은 유저 기기(iOS 단축어 "이미지에서 텍스트 추출", 안드로이드 렌즈)에서 끝난다.
2. **체결은 기록이 아니다.** 어떤 경로로 들어와도 `pending_trades`에 머물고, 유저가 "왜"(thesis) 한 줄을 붙여 승인해야 `trade_history`/`positions`에 반영된다. 승인 전 항목은 거울에 반영되지 않는다.
3. 시드 자본(`available_capital*`)은 가져오기로 건드리지 않는다 — 과거 체결을 일괄로 넣으면 자본 검증이 막기 때문. 자본은 기존 `/capital`로 유저가 관리.
4. 추천·조언 언어 없음. 파싱 결과는 사실(종목·수량·단가·시각)만.

## 데이터
- `import_batches(id, user_id, source csv|screenshot_text, broker_guess, filename, row_count, parsed_count, duplicate_count, unresolved_count, consent_at, created_at)`
- `pending_trades(id, batch_id, user_id, ticker?, name, action BUY|SELL, shares, price, currency, traded_at, confidence, status pending|approved|rejected|duplicate, dedupe_key, needs_ticker, raw_snippet, pre_trade_reflection_id?, approved_thesis[EncryptedText]?, approved_trade_id?, approved_at?, created_at)`
- `dedupe_key = sha256(user|ticker-or-name|action|shares|price|traded_at 분)`. 같은 키가 이미 있거나 `trade_history`에 같은 체결이 있으면 `duplicate`.
- 멈춤 매칭: 같은 유저·같은 티커의 `pre_trade_reflections` 중 `traded_at` 이전 7일 내 최신 → `pre_trade_reflection_id`. 없으면 null = "멈춤 없이 산 거래".

## API (`routes/imports.py`, prefix `/api/portfolio/imports`)
| 메서드 | 경로 | 본문 | 응답 |
|---|---|---|---|
| POST | `/` | multipart `file`(csv/xlsx/xls ≤2MB) + `consent=true` **또는** JSON `{text, source:"screenshot_text", consent:true}` | 201 `{batch, pending[], mapping, unmapped_headers}` |
| GET | `/pending` | — | `{pending[], count}` (status=pending, 최신순, ≤200) |
| PATCH | `/pending/<id>` | `{ticker?, name?, action?, shares?, price?, traded_at?}` | `{pending}` — dedupe·needs_ticker 재계산 |
| POST | `/pending/<id>/approve` | `{thesis}` 3~500자 필수 | `{ok, pending, trade_id, position_id}` |
| POST | `/pending/<id>/reject` | — | `{ok}` |

에러 코드: `IMPORT_CONSENT_REQUIRED` · `IMPORT_FILE_REQUIRED` · `IMPORT_FILE_TOO_LARGE`(413) · `IMPORT_UNSUPPORTED_FORMAT` · `IMPORT_NO_ROWS` · `IMPORT_THESIS_REQUIRED` · `IMPORT_TICKER_REQUIRED` · `IMPORT_SELL_EXCEEDS_HOLDING` · `IMPORT_NOT_PENDING`. 모두 `services.error_responses.api_error(en, kr, code, status)`.
데코레이터: `@api_auth` → `@general_rate_limit` → `@legal_scrub_response`.

## 파서 (`services/imports/`)
- `csv_parser.py` — 인코딩 utf-8-sig → utf-8 → cp949. xlsx는 openpyxl. **헤더 동의어 매핑**(증권사 fixture 없이 전 증권사 대응): 날짜(거래일자·체결일·일자·date…), 종목명(종목명·상품명…), 코드(종목코드·단축코드·티커·symbol…), 구분(거래구분·매매구분·side…: "매수" 포함→BUY, "매도" 포함→SELL, 입금·출금·배당 등은 skip), 수량, 단가, 금액(단가 없을 때 금액/수량), 통화. 숫자는 `,`·`₩`·`$`·`원` 제거. 날짜 `YYYY-MM-DD`·`/`·`.`·`YYYYMMDD` (+시간). 자체 export 포맷(`traded_at,ticker,name,action,shares,price_per_share,…`) 왕복 가능.
- `text_parser.py` — 체결 알림 텍스트 정규식. KR: `종목 N주 매수/매도 (체결) … N원`, US: `매수/매도|Bought|Sold N (shares) TICKER @ $P`. 줄마다 1건. 날짜 없으면 오늘, confidence 낮춤.
- 티커: 코드 → `normalize_ticker`; 종목명 → `kr_stock_registry.search` 정확 일치; 영문 1~6자 → US 티커; 못 찾으면 `needs_ticker=true`(UI에서 `API.market.search`로 수정).
- `ledger.py` — 승인 반영. BUY: 기존 포지션 가중평균(+USD면 fx 비용가중, `routes/portfolio.py:1810` 규칙 동일) / 없으면 새 Position(thesis=승인 문장, `added_at=traded_at`). SELL: 보유 초과 거부, pnl 계산, 전량이면 삭제. `TradeHistory` 1행(`traded_at` 스탬프). 자본 무변경.

## 프론트
- `/journal/import` 페이지: 동의 체크박스(수집 항목·목적·파기 명시, 옵트인) → 파일 선택 또는 텍스트 붙여넣기 → 결과 목록. `?text=` 쿼리로 프리필(manifest `share_target` GET, 안드로이드 공유 시트). iOS는 단축어 안내 문구.
- `/journal` 상단 `ImportInbox` 카드: 대기 N건, 행마다 종목·구분·수량·단가·시각·멈춤 매칭 표시 + thesis 입력 + 승인/거절. 승인은 thesis 비어 있으면 비활성.
- `endpoints.ts` `API.imports.*`, `hooks.ts` `usePendingImports()`, i18n `journal.import.*` (ko/en).

## 개인정보 (LOCAL_AGENT_LEGAL_RISK §5)
- 업로드 동의 체크박스 옵트인, 서버는 `consent_at` 기록.
- 원본 파일·텍스트는 파싱 후 저장하지 않는다(`raw_snippet` 300자만, 계좌번호 패턴 `\d{2,}-\d{2,}-\d{2,}`·`\d{8,}` 마스킹).
- 처리방침 "수집 항목"에 *이용자가 직접 업로드한 거래 정보* 추가.

## 테스트
- 백엔드 `tests/test_imports_route.py`: 동의 없음 400 · 한투식 헤더 CSV 파싱 · cp949 · 자체 export 왕복 · 토스 알림 텍스트 · 중복 표시 · needs_ticker → PATCH → 승인 · thesis 없으면 400 · 승인 후 Position/TradeHistory 생성 · 매도 초과 400 · 유저 격리.
- 프론트 vitest: `ImportInbox` 대기 행 렌더 + thesis 비면 승인 비활성.
