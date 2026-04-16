# Product Skills
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


## prd-write
- PRD 작성: 기능 요구사항 문서
- `유저 스토리, 수용 기준, 와이어프레임`

## feature-spec
- 기능 스펙: 상세 기능 명세서
- `입출력, 엣지 케이스, 의존성 정의`

## user-flow
- 유저 플로우: 사용자 여정 설계
- `화면 전환, 상태 변화, 에러 처리 플로우`

## backlog-groom
- 백로그 정리: 기능 목록 관리 및 우선순위
- `product_features.md 기반 정리`

## mvp-scope
- MVP 범위 정의: 최소 기능 세트 결정
- `필수 vs 있으면 좋은 기능 분류`
