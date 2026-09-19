# 브라우저 검증 — 2026-09-19 (B7 최초 수행)

`SHIP_BLOCKERS.md` B7 은 2026-09-12 이후 "브라우저 검증 7회 연속 불가" 로 이월돼 왔다.
이번에 실제 브라우저로 로그인 후 5개 화면을 걸었다. **B7 의 경로 자체는 통과했고, 신규 finding 은 아래 7건이다.**

## 재는 방법

```bash
# 백엔드 (.env 에 DEV_LOGIN_SECRET · FLASK_ENV=development · DATABASE_URL 없음 → 로컬 SQLite)
./venv/bin/python run.py                                   # :5050

# 프론트 — .env.local 의 NEXT_PUBLIC_DEMO_MODE=1 을 끄지 않으면 픽스처를 본다 (CLAUDE.md 함정 3)
cd frontend && NEXT_PUBLIC_DEMO_MODE=0 npm run dev         # :3000
```

로그인은 `POST /api/auth/dev-login` (`routes/dev_auth.py:29`).
⚠️ **동일 출처 프록시(`localhost:3000/api/...`)로 불러야 한다.** 프론트 CSP `connect-src` 는
`'self' https://*.onrender.com ...` 뿐이라 브라우저에서 `localhost:5050` 을 직접 부르면 차단된다 —
E2E 를 짤 때 여기서 한 번 막힌다.

측정 시각 2026-09-19 10:00~10:10 KST · 뷰포트 1280×900 · 로컬 SQLite(`pivoxquant.db`).

## 통과한 것 (실증)

| 항목 | 결과 |
|---|---|
| `/mirror` `/portfolio` `/pre-trade` `/journal` `/settings` 렌더 | 5/5 OK |
| 페이지가 호출한 API | 전부 200 (33건, 4xx/5xx 0) |
| 핵심 루프 end-to-end | `/pre-trade` 티커+thesis → 7문항 7/7 → START COOLDOWN → **04 기록 완료** |
| 기록 반영 | `/journal` 최하단에 신규 건 즉시 노출, 사이드바 카운터 `멈춤 0→1 / 진행 0→1` |
| 한글 입력 | 정상 (35자, 카운터·버튼 활성화 정상) |
| Import Inbox | 대기 7건 렌더, 승인/거절 UI 정상 |
| 거울 레이더 차트 | 9축 렌더 정상 |

## Finding

### P1 — 진짜 체결이 "미체결 알림"으로 조용히 버려진다
`services/imports/text_parser.py:99-104`. `_UNFILLED_FIELD` 가 단위 붙은 형태만 벗겨내서,
잔량이 단위 없이 붙은 라인이 통째로 스킵된다. **웹훅(준실시간) 경로 직격.**

```
SKIP  삼성전자 10주 매수 체결 71,200원 (미체결 0)
OK    삼성전자 10주 매수 체결 71,200원 미체결수량 0
SKIP  [키움증권] 삼성전자 10주 매수 체결 71,200원 잔량/미체결 0
```

`AUTOPILOT_BACKLOG.md:751` 에 P1 으로 올라 있고 `fix/import-order-notices` 소관으로 적혀 있으나,
해당 브랜치(`82f0d18d`)가 머지된 지금도 라이브 파서에서 재현된다. → **미해결.**

### P2 — NAV 타일이 로딩 중 `USD 0` 을 보여준다
`frontend/src/components/portfolio/v2/equity-curve-block.tsx:325`. 로딩 분기가 없어
`navKrw`/`navUsd` 가 아직 `undefined` 일 때 최종 fallback `fmtMoney(currentNav, currency)` →
`USD 0` 이 찍힌다. 같은 화면의 히어로는 `—` 로 정직하게 비우는데 이 타일만 **거짓 0** 을 낸다.
₩4,420,000 을 들고 있는 유저가 첫 1~2초 동안 `NAV USD 0` 을 본다. 재현 100%.

### P2 — 한국어 로케일에서 본문이 영어 (화면 간 불일치)
`<html lang="ko">`, 로케일 토글 `한국어` `aria-pressed=true` 상태에서:

- `/journal` `/mirror` — 본문 전부 한국어 ✅
- `/portfolio` — `Your book.` / `1 position observed · KRW 4,420,000 of capital · last observed just now. Cash buffer at 66.5%.` / `Total investable capital. Portfolio uses it for the cash buffer…` ❌
- `/settings` — 히어로 2문장 + 리드 문단 + 각 항목 설명(`Shown in the app and on your data exports.` 등) ❌
- `/pre-trade` — 완료 화면 전체(`You did the work. The record stands.` / `We stamped your reflection. PivoxQuant does not place trades — submit the order with your own broker.`) ❌, 카운터 `10 chars more required (0/10)` · `✓ 35 chars` ❌

`LONG ENTRY · 진입` 같은 **bilingual 키커는 의도된 컨벤션**이지만, 위는 유저가 읽어야 하는 문장이고
한국어 대응이 아예 없다. `/journal`·`/mirror` 이 제대로 한국어라 제품 내부가 서로 어긋난다.
가장 아픈 곳은 **7문항 완료 화면** — 제품에서 가장 중요한 확인 순간이 통째로 영어다.

### P2 — 사이드바: 제목 없는 최근 3건이 "최근 7일" 밑에 붙는다
`frontend/src/components/layout/sidebar-record-card.tsx:125` — `reflections.slice(0, 3)` 로
**날짜 윈도가 없다.** 바로 위가 `최근 7일 · 0일 기록` 이고 항목 날짜가 `6.10`(연도 없음)이라,
3개월 전 기록이 최근 것으로 읽힌다. 시각적 제목은 없고 `aria-label="최근 기록"` 만 있어
스크린리더와 눈으로 보는 것이 서로 다른 말을 한다.

### P3 — 시세를 쓰지 않는 화면에도 "한국 시세 데이터가 지연되고 있어요" 배너
`/pre-trade` `/settings` 에 뜬다. CLAUDE.md 핵심 3축은 시세를 한 번도 부르지 않는 것이 설계다.

### P3 — 체크박스 7개의 접근성 이름이 전부 동일
`I CONSIDERED THIS · 검토했음` ×7. `id`·`aria-label` 없이 label 로만 이름을 얻어,
스크린리더로는 어느 질문인지 구분할 수 없다.

### P3 — 삭제된 기능명 `Living CFO` 가 대시보드에 남아 있다
랜딩에서는 제거됐고(`top-nav.tsx:22`), 우산 문구 `당신 포트폴리오의 CFO` 는 CEO 승인(2026-09-10)이라
**그대로 두는 게 맞다.** 그런데 삭제된 쪽 이름이 대시보드에 아직 있다:
`portfolio/page.tsx:280` · `settings/page.tsx:335` 의 sticky `LIVING CFO` 바,
`components/ui/editorial.tsx:317` 의 푸터 `PivoxQuant · Living CFO` (전 화면).

## 문서 드리프트

- CLAUDE.md "알림 2종만 노출(price_52w · concentration)" → 실제 **3종**. 월간 미러 리포트가
  `c6ee4ead` 로 추가됐다. CLAUDE.md 의 알림 섹션을 갱신할 것.

## 확인 필요 (로컬 한정일 수 있음)

- 로컬 `pending_trades` id=6: 원문 `[한국투자증권] 해외주식 체결통보 TSLA 매수 2주 체결단가 250.00 USD …`
  이 `해외주식 / ₩250 / 티커없음` 으로 들어가 있고, id=7 에 같은 원문이 `TSLA / $250 / USD` 로 또 있다.
  **현재 파서는 정상 1건만 낸다**(재현 확인) — id=6 은 `e49a77de` 이전 파서가 남긴 잔재다.
  prod 에 같은 형태의 행이 남아 있는지, 있다면 정리 경로가 있는지 확인할 것.
- 경로 번호가 `02 The Deposition` → `04 Proceeded` 로 03 을 건너뛴다.
  `DEFAULT_COOLDOWN_SECONDS=0` 이라 쿨다운 단계가 생략되는 것으로 보이나, 유저에게는 누락으로 읽힌다.
