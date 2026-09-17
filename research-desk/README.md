# 리서치 데스크

질문 하나를 넣으면 에이전트가 **하위 질문으로 쪼개고 → 웹에서 근거를 모으고 → 반대 근거를 찾아 판정하고 → 출처가 달린 보고서**를 화면에 스트리밍한다.
PivoxQuant 와는 독립된 프로젝트다. 이 폴더만 떼어 새 저장소로 옮겨도 그대로 돈다.

## 왜 이렇게 만들었나

- **반증이 기본이다.** 조사 단계와 별개로 반증 단계가 "이 주장을 무너뜨릴 근거"를 따로 검색한다. 판정은 유지 / 기각 / 미결 셋뿐이고, 기각된 주장은 보고서에 사실처럼 쓰지 않는다.
- **출처 없는 숫자는 없다.** 추출 단계에서 모델이 실제로 열어 본 URL 이 아닌 출처는 버린다. 보고서 부록에 주장별 출처 번호와 반대 출처가 표로 붙는다.
- **서버는 아무것도 저장하지 않는다.** 보고서는 브라우저 localStorage 에만 남고 `.md` 로 내려받는다.
- **파이프라인은 네트워크를 모른다.** `pipeline.ts` 는 `Llm` 인터페이스 세 동작(`searchTurn` / `parseJson` / `streamText`)만 부른다. 실제 구현은 `llm.ts`, 테스트는 가짜 구현.

## 구조

```
src/lib/research/
  pipeline.ts   계획 → 조사(병렬) → 반증 → 판정 → 집필. 순수 오케스트레이션
  llm.ts        Anthropic 구현 — web_search / web_fetch 서버 도구, 구조화 출력, 스트리밍, server-side fallback
  prompts.ts    단계별 지시문 (한국어)
  schemas.ts    zod 스키마 (Plan / Claims / Verdicts)
  sources.ts    응답 블록에서 출처 URL 수집 (순수)
  report.ts     부록(주장 표·출처 목록) 렌더 (순수)
  sse.ts        이벤트 인코딩/디코딩 (서버·브라우저 공용)
src/app/api/research/route.ts   POST → text/event-stream
src/components/research-desk.tsx 화면
```

## 실행

```bash
cp .env.example .env.local   # ANTHROPIC_API_KEY 채우기
npm install
npm run dev                  # http://localhost:3000
```

검증:

```bash
npm run typecheck && npm run lint && npm test && npm run build
```

## 비용 감각

기본 모델은 `claude-opus-5`. 질문 하나 = 기획 1회 + (검색 턴 + 추출) × 하위 질문 4~5 + 반증 검색 1회 + 판정 1회 + 집필 1회. 검색 턴은 하위 질문당 웹 검색 최대 6회(`RESEARCH_MAX_SEARCHES`), 반증은 +2회. 비용을 낮추려면 `RESEARCH_MODEL=claude-sonnet-5`.

안전 분류기가 요청을 거절하면 서버가 대체 모델로 같은 요청을 다시 돌린다 (`fallbacks: "default"`). 끄려면 `llm.ts` 의 `base` 에서 `betas` 와 `fallbacks` 를 지운다.

## 배포

Vercel 에 그대로 올라간다. 환경변수 `ANTHROPIC_API_KEY` 만 넣으면 된다. API 라우트의 `maxDuration = 300` 은 플랜에 따라 상한이 다르니 확인할 것.

## 새 저장소로 떼어내기

```bash
# pivoxquant 루트에서
git subtree split --prefix=research-desk -b research-desk-only
# 새 저장소를 GitHub 에서 만든 뒤
git push git@github.com:<you>/research-desk.git research-desk-only:main
```
