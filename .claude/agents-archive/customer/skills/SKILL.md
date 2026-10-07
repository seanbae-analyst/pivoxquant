# Customer Skills
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


## feedback-analyze
- 피드백 분석: 유저 피드백 분류 및 우선순위
- `버그 / 기능요청 / UX이슈 / 칭찬 분류`

## onboarding-design
- 온보딩 설계: 신규 유저 첫 경험 최적화
- `회원가입 → 첫 화면 → 핵심 기능 안내`

## churn-prevent
- 이탈 방지: 이탈 신호 감지 및 대응
- `비활성 유저 리인게이지먼트`

## nps-survey
- NPS 서베이: 만족도 조사 설계/분석
- `추천 의향 0-10, 개선점 수집`
