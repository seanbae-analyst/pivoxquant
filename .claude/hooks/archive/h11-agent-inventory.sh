#!/usr/bin/env bash
# h11-agent-inventory.sh — SessionStart: dormant agent 추천 3개 출력
# rotation: 요일(0-6) 기반으로 추천 세트 순환

DAY=$(date +%u)  # 1=Mon … 7=Sun

cat <<'HEADER'
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[h11] 오늘의 dormant agent 추천
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HEADER

case $((DAY % 7)) in
  1)  # 월
    echo "  1. legal-kr-fintech  — 금융규제/§101/컴플라이언스 검토"
    echo "     호출: Task '법적 리스크 검토 해줘' + agent=legal-kr-fintech"
    echo "  2. verify-policy     — 약관/개인정보/이용제한 정책 검증"
    echo "     호출: Task '정책 문서 검증' + agent=verify-policy"
    echo "  3. brand-voice       — 카피/UI 문구 PivoxQuant 톤앤매너 점검"
    echo "     호출: Task '마케팅 문구 검토' + agent=brand-voice"
    ;;
  2)  # 화
    echo "  1. ux-researcher     — 온보딩/전환율/사용성 분석"
    echo "     호출: Task 'UX 개선 포인트 찾아줘' + agent=ux-researcher"
    echo "  2. verify-ux         — 실제 플로우 UX 검증 (클릭→결과 추적)"
    echo "     호출: Task 'UX 검증 해줘' + agent=verify-ux"
    echo "  3. onboarding-designer — 온보딩 스텝 디자인 개선"
    echo "     호출: Task '온보딩 개선안 만들어줘' + agent=onboarding-designer"
    ;;
  3)  # 수
    echo "  1. stripe-billing    — 결제/구독/환불/Webhook 이슈 처리"
    echo "     호출: Task '빌링 이슈 분석해줘' + agent=stripe-billing"
    echo "  2. billing-incident-handler — 결제 인시던트 대응 플레이북"
    echo "     호출: Task '결제 장애 대응' + agent=billing-incident-handler"
    echo "  3. compliance-gatekeeper — 출시 전 컴플라이언스 게이트 체크"
    echo "     호출: Task '출시 전 컴플라이언스 점검' + agent=compliance-gatekeeper"
    ;;
  4)  # 목
    echo "  1. verify-api        — 백엔드 API 계약/응답 구조 검증"
    echo "     호출: Task 'API 스펙 검증 해줘' + agent=verify-api"
    echo "  2. verify-data       — 데이터 정합성/FX/퀀트 수식 검증"
    echo "     호출: Task '데이터 검증 해줘' + agent=verify-data"
    echo "  3. verify-security   — 인증/권한/SQL injection 보안 검증"
    echo "     호출: Task '보안 검증 해줘' + agent=verify-security"
    ;;
  5)  # 금
    echo "  1. pdf-report-designer — PDF artifact 디자인/레이아웃 개선"
    echo "     호출: Task 'PDF 리포트 디자인 개선' + agent=pdf-report-designer"
    echo "  2. artifact-qa       — PDF/이메일/Brag Card artifact 품질 검사"
    echo "     호출: Task 'artifact 품질 검사' + agent=artifact-qa"
    echo "  3. email-deliverability — 이메일 전달률/SPF/DKIM/DMARC 점검"
    echo "     호출: Task '이메일 전달률 점검' + agent=email-deliverability"
    ;;
  6)  # 토
    echo "  1. mobile-pwa-optimizer — iOS/Android PWA 최적화"
    echo "     호출: Task 'PWA 모바일 최적화' + agent=mobile-pwa-optimizer"
    echo "  2. motion-designer   — 애니메이션/트랜지션 모션 스펙 점검"
    echo "     호출: Task '모션 디자인 개선' + agent=motion-designer"
    echo "  3. visual-designer   — UI 시각 퀄리티/여백/색상 일관성 점검"
    echo "     호출: Task '비주얼 디자인 점검' + agent=visual-designer"
    ;;
  0)  # 일
    echo "  1. persona-quant-domain — 페르소나별 퀀트 도메인 정합성 검토"
    echo "     호출: Task '페르소나 퀀트 검토' + agent=persona-quant-domain"
    echo "  2. regulatory-monitor — 금융규제 변화 모니터링"
    echo "     호출: Task '규제 변화 스캔' + agent=regulatory-monitor"
    echo "  3. growth            — 그로스 실험/퍼널/전환율 분석"
    echo "     호출: Task '그로스 분석 해줘' + agent=growth"
    ;;
esac

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  workhorse 현황: backend-dev / frontend-dev / bug-hunter / engineering"
echo "                  audit-code / investigator / qa / design / devops"
echo "  workflow 단축: wave-bug-hunt | wave-launch-prep | wave-design-polish"
echo "  (~/dev/pivoxquant/.claude/workflows/ 참조)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
