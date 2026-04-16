# Design Skills
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


## ui-review
- UI 검수: 디자인 시스템 준수 여부 확인
- `색상, 타이포, 간격, 컴포넌트 일관성`

## responsive-check
- 반응형 검수: 모바일/태블릿/데스크탑 대응
- `375px, 768px, 1280px 브레이크포인트`

## accessibility-audit
- 접근성 감사: WCAG 기준 체크
- `컬러 대비, 키보드 네비, 스크린리더, 터치타겟`

## design-system-update
- 디자인 시스템 관리: 컴포넌트/토큰 추가/수정
- `design_system.md 업데이트, 새 컴포넌트 가이드`

## dark-theme
- 다크 테마: 트레이딩 앱 다크 모드 최적화
- `차트 가시성, 색상 대비, 눈 피로도`
