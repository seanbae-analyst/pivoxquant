# 관찰 노트 (Observation Notes) — 빌드 계획

> 작성 2026-09-22. 상태: **v1 구현 완료 (2026-09-22, 브랜치 `feat/observation-notes`, 미푸시·미배포).** 계획 근거는 이 날짜의 코드 grep·Read 실측. 구현 이력·검증 수치는 `HANDOVER.md` v67.
> 제품 한 줄: 유저가 **거래 없이도** 주식 흐름을 읽다가 든 생각을 적어 두고, 그 노트가 나중에 같은 종목의 멈춤(pre-trade) 기록과 거울(mirror)에 되비치게 한다.

---

## 0. 왜 지금

- 지금 유저 텍스트가 저장되는 자리는 **거래에 묶인 순간**뿐이다 — `pre_trade_reflections.rationale`(사기 전 7문항), `positions.thesis`(보유 근거), `pending_trades.approved_thesis`(체결 import 승인). 관찰만 하고 있을 때 쓸 곳이 없다.
- `watchlist.note`, `position_dd_checks.note` 컬럼은 존재하지만 **쓰는 라우트가 없다**(export·삭제 캐스케이드만). 반쯤 죽은 자리다.
- 무료 베타의 질문은 *"한국 개인투자자가 기록을 하긴 하는가"*(CLAUDE.md §제품 전제). 거래 순간에만 기록을 허용하면 표본이 거래 빈도에 묶인다. 관찰 노트는 **기록의 진입 장벽을 거래 밖으로 낮춰** 이 질문의 표본을 늘린다.
- `docs/strategy/record-as-spine_2026-06-09.md` §4.2 루프 = **관측 → 성찰·기록 → 리뷰 → 복리.** "관측" 입력단이 기록에 먹이를 준다는 설계는 있었고, 실제 입력 표면은 없었다. 이 기능이 그 빈칸이다.

### 지켜야 할 제품 전제
- **멈춤(pre-trade) 마찰을 우회하는 통로가 되면 안 된다.** 관찰 노트는 기록의 *앞단*이고, 매수 결정은 여전히 `/pre-trade` 7문항을 거친다. 노트에서 "바로 주문" 류 동선을 만들지 않는다.
- **관측 톤.** 자본시장법 §6 — 시그널 라벨 BUY/SELL/HOLD 금지, 추천·조언 언어 금지(CLAUDE.md §중요 원칙). 노트는 유저 본인의 사적 기록이라 *유저 텍스트 자체*는 검열 대상이 아니지만, **우리가 붙이는 카피·플레이스홀더·라벨**은 전부 관측 톤이어야 한다.
- **시세를 부르지 않는다.** 3축(멈춤·기록·거울)은 시세 서비스를 import 하지 않는다. 관찰 노트도 같다. 벤더 시세 표시는 `MARKET_DATA_DISPLAY_ENABLED` 뒤에 있고 기본 꺼짐(2026-09-19)이므로 노트에 "그 시점 가격" 스냅숏을 넣는 설계는 **v1 에서 제외**.

---

## 1. 스코프

### v1 (이 계획의 범위)
1. `observation_notes` 테이블 + 마이그레이션 054
2. `/api/observation-notes` 생성·목록·단건·삭제·종목별 조회
3. `/journal` 상단 작성 박스 + 기존 멈춤 기록과 **한 타임라인에 섞어서** 표시(필터 칩)
4. `/pre-trade` 종목 선택 시 "이 종목 관찰 노트 N개 · 최근 발췌" 표시 — **관측 → 기록 연결**
5. `/portfolio` 보유 종목 행에서 종목 프리필로 노트 작성 진입
6. 데이터 내보내기·회원탈퇴 캐스케이드에 새 테이블 편입(PIPA)
7. 테스트 (백엔드 라우트·서비스, 프론트 vitest, 법적 스위트 green 유지)

### v1 에서 뺀 것 (의도)
- 노트 **수정**(PATCH). 멈춤 기록과 같은 **append-only + 삭제** 정책으로 시작 — 기록이 "거울"로 기능하려면 사후 편집 유혹이 적어야 한다. 수요가 확인되면 v2 에서 `edited_at` 과 함께.
- 전역 퀵캡처(FAB / 키보드 단축키). 진입점 2개(journal, portfolio)로 시작해 쓰는지 본다.
- 가격 스냅숏(`observed_context_json` 류). 위 §0 시세 전제.
- 서버 통합 피드 엔드포인트. v1 은 프론트에서 두 훅을 병합. 페이지네이션이 아파지면 v2.
- 행동 점수(`scorer.py::_reflection_rate_subscore`) 반영. 아래 §4.

---

## 2. 데이터 모델

파일 `models/observation_note.py`, 테이블 `observation_notes`. 템플릿은 `models/pre_trade_reflection.py:58-110`.

| 컬럼 | 타입 | 규칙 |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | FK `users.id` ondelete CASCADE, index | 소유 필터는 **서비스 층**에서 (pre_trade 관례) |
| `body` | `EncryptedText` (`services/crypto_service.py:366`) | 공백 제거 후 1자 이상, **최대 5000자** (`friction.py:70 MAX_TEXT_CHARS` 와 동일 상수 재사용) |
| `tickers_json` | TEXT (JSON array) | **0~5개**, 각 `services/ticker_normalizer.normalize_ticker` 로 정규화, 길이 ≤20. 빈 배열 허용 = 시장 전반 노트 |
| `tags_json` | TEXT (JSON array) | 0~10개, 각 ≤40자 — `weekly_pulse.topics` 캡(`routes/profile.py` `_PULSE_TOPIC_MAX/_PULSE_TOPIC_LEN`)과 동일 |
| `source` | String(20) | `journal` \| `portfolio` \| `pre_trade` — 어느 표면에서 썼는지. 베타 질문("어디서 기록하나")의 계측 |
| `created_at` | DateTime(tz) | index (`user_id, created_at desc` 복합) |

**넣지 않는 것**: `updated_at`(수정 없음), `linked_reflection_id`. 멈춤 기록과의 연결은 **읽기 시점에 (ticker, 시간창) 으로 계산**한다 — 노트를 불변으로 두고, 나중에 창 폭을 바꿔도 데이터 마이그레이션이 없다.

`to_dict()` 는 `intended_name` 관례처럼 `services/name_resolver.resolve_stock_name` 으로 `tickers[].name` 을 붙인다.

### 마이그레이션
- `migrations/versions/054_observation_notes.py` (선행 `053_age_self_declaration`).
- ⚠️ 함정 1: 로컬 빈 DB 는 `create_all` 1회 부팅 후 `flask db stamp head`.
- ⚠️ 함정 13: `app.py::_do_migrations`(`:534,:549`) 에 DDL 을 넣을 일은 없다 — 새 테이블은 alembic + create_all 로 충분. 넣지 마라.
- `tests/test_migration_round_trip.py:123-129` 스팟체크 목록에 `observation_notes` 한 줄 추가(선택이지만 권장 — 048 처럼 EncryptedText 폭 문제가 재발하면 여기서 잡힌다).

---

## 3. 백엔드 API

블루프린트 `routes/observation_notes.py`, `url_prefix="/api/observation-notes"`, `routes/__init__.py` 에 등록. 응답은 `routes/pre_trade.py:54 _envelope` 와 **같은 모양**(`{"ok": true, "disclaimer": …, …}`) — 스크린샷이 돌아도 면책 문구가 붙게. 에러는 `services/error_responses.api_error`.

| Method · Path | 데코레이터 | 입력 | 응답 / 에러 |
|---|---|---|---|
| `POST /` | `@api_auth` `@general_rate_limit` | `{body, tickers?: [], tags?: [], source?}` | 201 `{note}` · `OBS_NOTE_BAD_INPUT` 400 |
| `GET /list` | `@api_auth` | `?limit=`(기본 50, 상한 200) `?before=<id>`(커서) `?ticker=` `?tag=` | `{notes: [...], next_before}` |
| `GET /<id>` | `@api_auth` | | `{note}` · `OBS_NOTE_NOT_FOUND` 404 (타인 것도 404, 존재 노출 금지) |
| `DELETE /<id>` | `@api_auth` `@general_rate_limit` | | 200 `{deleted: id}` · 404 |
| `GET /by-ticker/<ticker>` | `@api_auth` | `?days=`(기본 30) `?limit=`(기본 5) | `{ticker, count, notes}` — `/pre-trade` 가 부른다 |

서비스 `services/observation_notes/service.py`: `create_note`, `list_notes`, `get_note`, `delete_note`, `notes_for_ticker`. 검증(캡·정규화·비객체 body 400)은 서비스에, 라우트는 얇게 — `friction.py` 와 동일 분업.

**법적 스크럽 결정**: `routes/behavior.py` 의 거울 라우트는 `@legal_scrub_response` 를 쓰지만 `routes/pre_trade.py` 는 안 쓴다(유저 본인 텍스트를 되돌려주는 라우트). 관찰 노트도 **pre_trade 를 따른다** — 유저의 사적 기록을 서버가 고쳐서 돌려주면 "기록"이 아니다. 단 `tests/test_legal_*` 스위트(함정 4)가 새 라우트 추가로 빨개지는지 반드시 돌려 확인.

### PIPA 배선 (빠뜨리면 prod 500 전과 있음 — `routes/auth.py:1745` 주석)
- `routes/auth.py:1723 purge_ops` 에 `("observation_notes", …)` 추가. 주석대로 `scripts/nightly/pipa_purge._delete_user_cascade` 도 **같이**.
- `routes/profile.py` 데이터 내보내기(`:2015~`, `:2560~` 의 dataset 분기)에 `observation_notes` dataset 추가 — 상한 상수 `_EXPORT_OBS_NOTE_LIMIT` 를 DD_CHECK 관례로.

---

## 4. 거울(mirror) · 멈춤(pre-trade) 연결 — 이게 "메모장"과의 차이

1. **멈춤 화면에 되비추기 (v1 필수).** `frontend/src/components/pre-trade/pre-trade-friction-core.tsx` `usePreTradeCycle`(`:143`) 의 `setup` 단계에서 종목이 정해지면 `by-ticker` 를 불러 `QuestionsStep`(`:370`) 위에 한 줄: *"이 종목에 대해 최근 30일 관찰 노트 3개 · 「…」"*. 유저가 자기 과거 관찰을 보며 7문항을 쓴다. 이것이 §0 루프의 "관측 → 성찰·기록" 화살표다. 카피는 관측 톤, 노트 내용은 그대로 인용.
2. **기록 화면 요약 (v1).** `/journal` 상단에 카운트만: 이번 주 관찰 노트 N개 · 종목 M개. 점수·라벨 없음.
3. **행동 점수는 v1 에서 건드리지 않는다.** `services/behavior/scorer.py:334 _reflection_rate_subscore` 는 "거래당 사전 기록 사용률"이라 의미가 다르다. 관찰 노트를 섞으면 지표 정의가 바뀐다. **v2 후보**: 별도 거울 `observation_link_mirror` — "노트를 쓴 종목 중 이후 N일 안에 거래한 비율 / 노트 없이 거래한 비율". 이건 `friction_outcome.py` 와 같은 결의 *"기록이 행동을 바꿨나"* 질문이고, 데이터가 쌓인 뒤에만 의미가 있다.

---

## 5. 프론트엔드

### 배선
- `frontend/src/lib/endpoints.ts` — `API.observationNotes.{list, create, detail(id), byTicker(ticker)}`. ⚠️ URL 변경 금지·심볼로 소비자 추적 원칙.
- `frontend/src/lib/types.ts` — `ObservationNote`, `ObservationNotesResponse`, `ObservationNotesByTickerResponse`.
- `frontend/src/lib/hooks.ts` — `useObservationNotes(limit, {ticker?, tag?})`, `useObservationNotesByTicker(ticker | null, days=30)` — `usePreTradeJournal`(`:169`) 과 같은 SWR 옵션(`revalidateOnFocus:false`, `dedupingInterval:30_000`). 생성·삭제는 `lib/api.ts apiFetch` 후 두 훅 `mutate`.

### 컴포넌트 (`frontend/src/components/journal/`)
- `observation-note-composer.tsx` — `<textarea>` + 글자수(기존 `Field` 패턴, 리치 에디터 없음) + 종목 칩(0~5) + 태그 입력(0~10). props: `defaultTickers`, `source`, `onCreated`. 플레이스홀더 예: *"지금 보고 있는 흐름을 그대로 적어 두세요. 나중에 이 종목을 멈춤 화면에서 만나면 이 글이 다시 보입니다."* — 추천·조언 어휘 금지.
- `observation-note-card.tsx` — 본문·종목 칩·태그·상대시각(`journal/page.tsx` 의 `entryTimestamp`/`absoluteDate` 재사용)·삭제(확인 1회).
- `components/shared/ticker-search.tsx` — **추출**. 지금 유일한 자동완성은 `portfolio/v2/add-position-modal-v2.tsx:132-170` 안에 raw `fetch` 로 박혀 있다(`regression-guards: allow-raw-fetch` 주석). 공용 컴포넌트로 빼서 composer 와 add-position 둘이 쓴다. `/api/search` 는 시세 플래그 예외라 꺼진 상태에서도 동작(`routes/market.py:40`).

### `/journal` 타임라인 병합
`journal/page.tsx` 는 지금 reflection 만 시간역순으로 그린다. 두 훅 결과를 `{kind: "reflection" | "note", ts, payload}` 로 정규화해 정렬하는 순수 함수 `mergeTimeline()` 을 `journal/timeline.ts` 로 빼고 `__tests__/timeline.test.ts` 로 잠근다. 상단 필터 칩: **전체 · 멈춤 기록 · 관찰 노트**. 6개 거울 컴포넌트·weekly pulse·import inbox 배치는 그대로.

### 진입점
- `/journal` 상단 composer (`source=journal`).
- `/portfolio` 보유 행 액션 "관찰 노트" → composer 모달, `defaultTickers=[ticker]`, `source=portfolio`.
- `/pre-trade` 는 **읽기만**(§4-1). 여기서 노트를 쓰게 하면 7문항을 피하는 통로가 된다.

### 규칙 체크
- 디자인 v3 토큰만(`src/__tests__/design-token-drift` 가 잡는다). 모바일 하단 바(`bottom-nav.tsx`) 는 건드리지 않는다 — 진입점은 기존 화면 안.
- `DisclaimerBanner` 는 `(dashboard)/layout.tsx` 가 이미 마운트 — 페이지 안 중복 금지.
- 사용자 노출 tsx 에 BUY/SELL 리터럴 금지(`lib/pre-trade.ts` 브리지).
- `.env.local` `NEXT_PUBLIC_DEMO_MODE=1` 이면 fixture 를 본다(함정 3) — 데모 fixture 에도 노트 샘플 2~3개 추가해야 데모 화면이 빈칸이 안 된다.

---

## 6. 테스트

### 백엔드 `tests/test_observation_notes.py` (템플릿 `tests/test_pre_trade_friction.py:289-359,652`)
- 서비스: 캡(5000자·종목 5·태그 10·태그 40자), 종목 정규화, 빈 body 400, 비객체 body 400, `by-ticker` 시간창·정렬.
- 라우트(`client` + `auth_user`): 생성 201 + disclaimer 존재, 목록이 타인 노트 제외, 단건·삭제가 타인 것에 404, `raw_client` 로 CSRF 미첨부 시 거절(conftest 래퍼는 DELETE 도 감싼다 — `:37`), 커서 페이지네이션.
- PIPA: 탈퇴 후 `ObservationNote.query.filter_by(user_id)` 0건 · 내보내기 응답에 dataset 포함.
- `tests/test_migration_round_trip.py` 스팟체크 1줄.
- 법적 스위트 7파일(CLAUDE.md 함정 4) 전부 green.

### 프론트 (vitest, `__tests__/` 콜로케이션)
- `journal/__tests__/timeline.test.ts` — 병합 정렬·kind 태깅·빈 입력.
- `components/journal/__tests__/observation-note-composer.test.tsx` — 빈 본문 제출 차단, 캡 표시, 종목 5개 초과 차단.
- `components/shared/__tests__/ticker-search.test.tsx` — 디바운스·선택 후 요청 중단(기존 `picked`/`AbortController` 동작 보존).
- 기존 리포 가드(`ai-label-coverage`, `design-token-drift`) 통과.

### 완료 판정 커맨드 (CLAUDE.md §이 파일을 믿기 전에)
```bash
./venv/bin/python -m pytest -q | tail -2
cd frontend && npx vitest run && npx tsc --noEmit && npm run lint && npm run build
```

---

## 7. 순서와 크기 (1인 기준, 실측 아님 — 추정)

| 단계 | 내용 | 크기 |
|---|---|---|
| P1 백엔드 | 모델·054·서비스·라우트·PIPA 배선·테스트 | 1일 |
| P2 프론트 기반 | endpoints/types/hooks · ticker-search 추출 · composer · card | 1일 |
| P3 journal 병합 | `mergeTimeline` · 필터 칩 · 상단 카운트 · 데모 fixture | 0.5일 |
| P4 척추 연결 | pre-trade 종목별 노트 표시 · portfolio 행 진입점 | 0.5일 |
| P5 마감 | 법적 스위트 · 빌드 · HANDOVER 한 줄 · 이 문서 상태 갱신 | 0.5일 |

P1 → P2 는 순서 의존. P3·P4 는 P2 뒤 병렬 가능. 커밋은 단계별로 쪼갠다(`feat(observation-notes): …`).

---

## 8. 열린 질문 — 답 없으면 아래 가정으로 간다

| # | 질문 | v1 가정 |
|---|---|---|
| Q1 | 노트 수정 허용? | **불허(append-only + 삭제).** 멈춤 기록과 정책 통일 |
| Q2 | 종목 없는 시장 전반 노트 허용? | **허용**(tickers 0개). 관찰은 종목 밖에서도 일어난다 |
| Q3 | journal 에서 별도 탭 vs 한 타임라인? | **한 타임라인 + 필터 칩.** "기록"은 하나라는 제품 언어 |
| Q4 | 행동 점수(기록 습관)에 반영? | **v1 반영 안 함.** 카운트만 노출. §4-3 |
| Q5 | 노트 본문에 금칙어(추천·조언) 검사? | **안 함.** 유저 사적 기록. 우리 카피만 검사 대상. 법률 검토 큐(`legal_question_queue.md`)에 "UGC 되비침이 §6 표시에 해당하나" 1줄 등록 |

---

## 9. 리스크
- **7문항 우회 통로화** — pre-trade 에서 노트 작성 진입점을 만들지 않는 것으로 막는다(§5 진입점).
- **"기록"의 희석** — 멈춤 기록은 거래 결정의 증거, 관찰 노트는 그 앞단. 타임라인에서 `kind` 라벨·아이콘으로 구분을 유지하고 카운트도 따로 낸다.
- **PIPA 누락** — `purge_ops` 와 nightly purge 스크립트 두 곳 동기화. 테스트로 잠근다.
- **EncryptedText 폭** — 048 에서 넓힌 전례. 마이그레이션에서 처음부터 `EncryptedText` 를 쓰고 round-trip 테스트에 걸어 둔다.
