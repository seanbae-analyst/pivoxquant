# 제품 전제 — 불리한 근거를 먼저 본다 (전문)

> CLAUDE.md 에서 옮겨 온 원문 (2026-09-11). CLAUDE.md 에는 결론 두 줄만 남겼다.
> 코드 주석의 "CLAUDE.md §제품 전제" 는 이 문서를 가리킨다.

메모리: `~/.claude/projects/-Users-seanbae-Desktop----pivoxquant/memory/`
(`MEMORY.md` 가 인덱스). 조사는 `research_habit_premise.md` /
`research_substitute_threat.md` / `research_toss_openapi.md`.

- **"질문을 던진다"는 차별화가 아니다** — ChatGPT Study Mode(2025-07-29)가 전 플랜
  무료로 제공한다.
- **"자동 수집"도 해자가 아니다** — 키움 자동일지, MyData 금투-003, 도미노가 이미
  커버한다.
- **비-아첨 해자는 2026-09-01 기준 사실상 소멸했다.** 8-30 메모는 "12~18개월
  시한부"로 봤지만, [lechmazur/sycophancy](https://github.com/lechmazur/sycophancy/)
  (2026-08-05 갱신) 실측은 GPT-5.6 Terra **0.0%** / Claude Fable 5 **0.5%**(결단
  커버리지 77.3%)다. 프론티어 모델이 이미 아첨하지 않으면서 판단을 내린다.
- **수요 신호가 나쁘다** — 한국 매매일지 앱 카테고리에 승자가 없다. 동일 컨셉
  '살래말래'가 출시 9개월에 평가 5개.

**남은 진짜 자산은 "일어나지 않은 거래"다.** 증권사도 MyData 도 체결만 알지
*사려다 말았는지*를 모르고, ChatGPT 는 유저가 매번 다시 붙여넣지 않는 한 모른다 —
그리고 안 산 거래를 붙여넣는 사람은 없다. 이걸 계산하는 게
`services/pre_trade/friction_outcome.py` 이고,
`scripts/friction_outcome_report.py` 로 바로 돌려볼 수 있다.

**다음 세션이 답해야 할 질문은 코드가 아니다** — *"한국 개인투자자가 기록을
하긴 하는가."* 직접 통계가 존재하지 않아 조사로는 못 푼다. 무료 베타의 목적을
수익이 아니라 **이 질문의 답을 얻는 것**에 두는 게 맞다.
