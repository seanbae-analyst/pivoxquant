# Strategy Skills
## ⚖️ Iron Rules (필수 — sub-skill 사용 시 절대 위반 금지)

1. **No assumption skipping** — "충돌 우려" "범위 밖일 듯" 같은 추측으로 스킵 금지. 의심되면 caller에게 escalate.
2. **Partial ≠ Complete** — 7개 중 4개만 끝났으면 "완료" 아님. INCOMPLETE 보고 + 남은 N개 명시.
3. **Reasoning ≠ Verification** — 도구 권한 거부됐으면 "수학적으로 검증" 금지. 즉시 "BLOCKED: <tool>" 명시 + 수동 검증 요청.
4. **Evidence required** — "OK" "정상" "통과" 보고 시 반드시 증거 첨부 (curl 응답 / file diff / build exit code / DOM snapshot).
5. **Brand: PivoxQuant** (NOT stockpilot) — 모든 출력 통일.
6. **Permission denied = ESCALATE** — 침묵 금지. "Bash 거부됨, 사용자 직접 실행 요청" 명시.

## 완료 보고 템플릿 (필수)

```
## ✅ Completion Checklist
- [ ] 항목 1: ✅완료/❌미완(이유)
- [ ] 항목 2: ...
- [ ] 모든 항목 verified (증거 첨부): ✅/❌

## Status: COMPLETE / INCOMPLETE / BLOCKED
```

---


## roadmap-review
- 로드맵 검토: 현재 진행 상황 대비 계획 점검
- `Phase 1(MVP) → 2(유저확보) → 3(차별화) 추적`

## feature-prioritize
- 기능 우선순위: Impact vs Effort 매트릭스
- `RICE 스코어링, MoSCoW 분류`

## market-analysis
- 시장 분석: 경쟁사 및 시장 트렌드
- `개인 투자자 앱 시장, 차별화 포인트`

## pivot-evaluate
- 피벗 평가: 방향 전환 필요성 검토
- `데이터 기반 Go/No-Go 판단`
