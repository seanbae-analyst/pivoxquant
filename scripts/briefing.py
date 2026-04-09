#!/usr/bin/env python3
"""
StockPilot CEO Briefing System
Generates and sends HTML email briefings via SendGrid.

Usage:
    python scripts/briefing.py morning|noon|evening
"""

import os
import sys
import glob
import random
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent                         # stockpilot/
AGENTS_DIR = PROJECT_ROOT.parent / ".claude" / "agents"  # ../../.claude/agents/

KST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# Data collection helpers
# ---------------------------------------------------------------------------

def collect_departments() -> list[dict]:
    """Return list of dicts: {name, has_agent_md, has_skill, skill_path}."""
    departments = []
    if not AGENTS_DIR.is_dir():
        return departments

    for entry in sorted(AGENTS_DIR.iterdir()):
        if entry.name.startswith(".") or entry.name == "README.md":
            continue
        if entry.is_dir():
            agent_md = entry.parent / f"{entry.name}.md"
            skill_path = entry / "skills" / "SKILL.md"
            departments.append({
                "name": entry.name,
                "has_agent_md": agent_md.is_file(),
                "has_skill": skill_path.is_file(),
            })
        elif entry.is_file() and entry.suffix == ".md" and entry.name != "README.md":
            name = entry.stem
            dir_path = entry.parent / name
            if not dir_path.is_dir():
                departments.append({
                    "name": name,
                    "has_agent_md": True,
                    "has_skill": False,
                })
    # deduplicate by name
    seen = set()
    unique = []
    for d in departments:
        if d["name"] not in seen:
            seen.add(d["name"])
            unique.append(d)
    return unique


def count_agents() -> int:
    if not AGENTS_DIR.is_dir():
        return 0
    return len(list(AGENTS_DIR.glob("*.md"))) - (1 if (AGENTS_DIR / "README.md").is_file() else 0)


def count_skills() -> int:
    if not AGENTS_DIR.is_dir():
        return 0
    return len(list(AGENTS_DIR.glob("*/skills/SKILL.md")))


def git_log(n: int = 5) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--oneline", "--no-decorate"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=10,
        )
        return [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    except Exception:
        return ["(git log unavailable)"]


def git_log_today() -> list[str]:
    today = datetime.now(KST).strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--no-decorate", f"--since={today}T00:00:00+09:00"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=10,
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        return lines if lines else ["(No commits today yet)"]
    except Exception:
        return ["(git log unavailable)"]


def check_build() -> str:
    """Quick build check — tries to import the app."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import app"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30,
        )
        return "PASS" if result.returncode == 0 else "FAIL"
    except Exception:
        return "UNKNOWN"


# ---------------------------------------------------------------------------
# Inspiration content pools
# ---------------------------------------------------------------------------

NEW_DEPT_IDEAS = [
    ("Risk Management", "VaR 분석, 포트폴리오 리스크 모니터링, 손절 자동화 에이전트"),
    ("Data Pipeline", "실시간 데이터 수집/전처리/캐싱 전담 에이전트"),
    ("Compliance AI", "금융 규제 자동 체크, 투자 권유 문구 검증 에이전트"),
    ("UX Research", "사용자 행동 분석, A/B 테스트 자동화, 히트맵 분석 에이전트"),
    ("Content Studio", "블로그/뉴스레터/SNS 콘텐츠 자동 생성 에이전트"),
    ("Partnership", "API 파트너 탐색, 제휴 제안서 자동 생성 에이전트"),
    ("Localization", "다국어 지원 자동화, 현지화 품질 관리 에이전트"),
    ("Revenue Ops", "결제/구독/환불 관리, 매출 분석 자동화 에이전트"),
    ("AI Trainer", "모델 파인튜닝 데이터 수집, 프롬프트 최적화 에이전트"),
    ("Community", "디스코드/포럼 관리, 유저 피드백 수집 자동화 에이전트"),
]

CLAUDE_CODE_TIPS = [
    {
        "title": "MCP Server 활용",
        "body": "Claude Code에서 MCP(Model Context Protocol) 서버를 연결하면 외부 도구와 실시간 연동이 가능합니다. "
                "예: Obsidian MCP로 노트 검색, GitHub MCP로 이슈 관리, Supabase MCP로 DB 직접 조회.",
    },
    {
        "title": "Obsidian 연동 팁",
        "body": "Obsidian MCP를 설정하면 Claude가 직접 노트를 읽고/쓰고/검색할 수 있습니다. "
                "일일 노트에 자동으로 작업 로그를 기록하거나, 위키 문서를 Claude가 참조하게 설정해보세요.",
    },
    {
        "title": "bkit PDCA 워크플로",
        "body": "bkit의 Plan-Do-Check-Act 사이클을 활용하면 기능 개발을 체계적으로 관리할 수 있습니다. "
                "/pdca status로 현황 확인, /pdca next로 다음 단계 진행. 모든 결정이 감사 로그에 남습니다.",
    },
    {
        "title": "Git Hooks 자동화",
        "body": "Claude Code의 hooks 기능으로 커밋 전 자동 린트, 푸시 전 테스트 실행 등을 설정할 수 있습니다. "
                ".claude/settings.json에서 PreCommit, PrePush 훅을 정의해보세요.",
    },
    {
        "title": "Agent 시스템 최적화",
        "body": "각 에이전트(.md)에 명확한 역할과 권한을 정의하면 Claude가 컨텍스트를 더 잘 이해합니다. "
                "skills/ 폴더에 SKILL.md를 추가하면 에이전트 전용 기능을 부여할 수 있습니다.",
    },
    {
        "title": "Memory 시스템 활용",
        "body": ".claude/memory/ 폴더에 프로젝트 메모리를 저장하면 대화 간에도 컨텍스트가 유지됩니다. "
                "MEMORY.md에 핵심 결정사항, 아키텍처, 규칙을 기록해두면 모든 세션에서 참조됩니다.",
    },
    {
        "title": "Scheduled Tasks",
        "body": "Claude Code의 scheduled-tasks MCP를 사용하면 정기적인 작업을 자동화할 수 있습니다. "
                "cron 표현식 또는 1회성 fireAt으로 코드 리뷰, 보고서 생성 등을 예약해보세요.",
    },
    {
        "title": "워크트리(Worktree) 활용",
        "body": "복잡한 기능 개발 시 worktree를 사용하면 현재 작업을 방해하지 않고 별도 브랜치에서 실험할 수 있습니다. "
                "'worktree에서 작업해줘'라고 요청하면 자동으로 격리된 환경이 생성됩니다.",
    },
]

BIZ_IDEAS = [
    "프리미엄 알림 서비스: 실시간 매매 신호를 카카오톡/텔레그램으로 전송하는 유료 구독 기능 ($9.99/월)",
    "소셜 트레이딩: 상위 수익률 유저의 포트폴리오를 복사하는 기능 (수수료 모델)",
    "증권사 파트너십: 한국투자증권/키움증권 API 연동으로 원클릭 매매 실행",
    "교육 콘텐츠: 퀀트 투자 기초부터 알고리즘 트레이딩까지 동영상 강의 번들",
    "백테스트 마켓플레이스: 유저가 자신의 전략을 공유/판매하는 플랫폼",
    "기관 투자자 대시보드: B2B SaaS로 확장 — 기관 전용 분석 도구 월 $299부터",
    "AI 포트폴리오 어드바이저: GPT 기반 개인 맞춤형 투자 조언 (프리미엄 기능)",
    "뉴스 센티먼트 알파: 뉴스/SNS 감성 분석으로 시장 방향 예측하는 독자 데이터 상품",
    "암호화폐 확장: 주식 외에 코인 시장도 지원하여 TAM(Total Addressable Market) 확대",
    "API-as-a-Service: StockPilot의 퀀트 분석 엔진을 외부 개발자에게 API로 제공 ($0.01/call)",
    "리밸런싱 자동화: 목표 포트폴리오 비율을 설정하면 자동으로 리밸런싱 실행",
    "연금/ISA 최적화: 한국 세제혜택 계좌에 특화된 투자 전략 추천 기능",
]


# ---------------------------------------------------------------------------
# HTML email template
# ---------------------------------------------------------------------------

def html_wrapper(title: str, body_sections: str, now: datetime) -> str:
    date_str = now.strftime("%Y-%m-%d %H:%M KST")
    return f"""\
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#050508;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#050508;">
<tr><td align="center" style="padding:24px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background-color:#0d0d12;border-radius:12px;overflow:hidden;border:1px solid #1a1a2e;">

<!-- Header -->
<tr><td style="background:linear-gradient(135deg,#050508 0%,#0d1117 100%);padding:32px 24px;text-align:center;border-bottom:2px solid #10b981;">
  <h1 style="margin:0;font-size:24px;color:#10b981;letter-spacing:1px;">StockPilot</h1>
  <p style="margin:8px 0 0;font-size:14px;color:#6b7280;">{title}</p>
  <p style="margin:4px 0 0;font-size:12px;color:#4b5563;">{date_str}</p>
</td></tr>

<!-- Body -->
<tr><td style="padding:24px;">
{body_sections}
</td></tr>

<!-- Footer -->
<tr><td style="padding:16px 24px;text-align:center;border-top:1px solid #1a1a2e;">
  <p style="margin:0;font-size:11px;color:#4b5563;">
    Automated by StockPilot Engineering &middot; Powered by SendGrid
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def section(emoji: str, title: str, content: str) -> str:
    return f"""\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
<tr><td style="padding:12px 16px;background-color:#111827;border-radius:8px;border-left:3px solid #10b981;">
  <h2 style="margin:0 0 12px;font-size:16px;color:#f3f4f6;">{emoji} {title}</h2>
  <div style="font-size:14px;color:#d1d5db;line-height:1.6;">
    {content}
  </div>
</td></tr>
</table>"""


def make_table(headers: list[str], rows: list[list[str]]) -> str:
    hdr = "".join(
        f'<th style="padding:8px 12px;text-align:left;font-size:12px;color:#9ca3af;'
        f'border-bottom:1px solid #1f2937;font-weight:600;">{h}</th>'
        for h in headers
    )
    body = ""
    for row in rows:
        cells = "".join(
            f'<td style="padding:8px 12px;font-size:13px;color:#e5e7eb;'
            f'border-bottom:1px solid #111827;font-family:monospace;">{c}</td>'
            for c in row
        )
        body += f"<tr>{cells}</tr>"
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin:8px 0;">'
        f"<tr>{hdr}</tr>{body}</table>"
    )


def stat_card(label: str, value: str, color: str = "#10b981") -> str:
    return (
        f'<div style="display:inline-block;width:30%;min-width:140px;margin:4px;'
        f'padding:12px;background:#111827;border-radius:8px;text-align:center;">'
        f'<div style="font-size:24px;font-weight:700;color:{color};font-family:monospace;">{value}</div>'
        f'<div style="font-size:11px;color:#6b7280;margin-top:4px;">{label}</div>'
        f'</div>'
    )


def bullet_list(items: list[str]) -> str:
    li = "".join(f"<li style='margin:4px 0;color:#d1d5db;'>{item}</li>" for item in items)
    return f"<ul style='margin:0;padding-left:20px;'>{li}</ul>"


def code_block(lines: list[str]) -> str:
    text = "<br>".join(lines)
    return (
        f'<div style="background:#0a0a0f;border:1px solid #1f2937;border-radius:6px;'
        f'padding:12px;font-family:monospace;font-size:12px;color:#a3e635;'
        f'overflow-x:auto;white-space:pre-wrap;">{text}</div>'
    )


# ---------------------------------------------------------------------------
# Briefing builders
# ---------------------------------------------------------------------------

def build_morning(now: datetime) -> str:
    depts = collect_departments()
    commits = git_log(5)
    build_status = check_build()
    n_agents = count_agents()
    n_skills = count_skills()

    # Section 1: Project status
    build_color = "#10b981" if build_status == "PASS" else "#ef4444"
    build_emoji = "PASS" if build_status == "PASS" else "FAIL"
    s1 = section("📋", "프로젝트 현황", (
        f'<div style="margin-bottom:12px;">'
        f'{stat_card("Total Agents", str(n_agents))}'
        f'{stat_card("Total Skills", str(n_skills))}'
        f'{stat_card("Build", build_emoji, build_color)}'
        f'</div>'
        f'<p style="margin:8px 0 4px;font-size:13px;color:#9ca3af;font-weight:600;">Recent Commits</p>'
        f'{code_block(commits)}'
    ))

    # Section 2: Org chart (C-level structure)
    dept_names = {d["name"] for d in depts}
    org = [
        ("🧠 CTO", "기술 총괄", [
            "frontend-dev", "backend-dev", "realtime-dev", "infra-dev",
            "performance", "security", "qa", "code-janitor",
            "import-police", "dead-code-hunter", "style-enforcer", "architecture-guard",
        ]),
        ("💰 CFO", "재무 총괄", ["finance", "ir", "revenue-ops"]),
        ("📦 CPO", "제품 총괄", ["product", "design", "onboarding", "i18n"]),
        ("📈 CMO", "마케팅 총괄", ["marketing", "growth", "customer", "competitive-intel"]),
        ("⚖️ CLO", "법무 총괄", ["legal", "compliance-ai"]),
        ("📊 CDO", "데이터 총괄", ["analytics", "quant"]),
        ("🏢 COO", "운영 총괄", ["operations", "hr", "docs"]),
    ]
    ceo_direct = ["strategy", "pitch", "audit", "user-tester"]
    # Department descriptions — what each dept does / did recently
    dept_desc = {
        "frontend-dev": "Next.js UI 구현 · Detail 7탭 완료",
        "backend-dev": "Flask API · Google OAuth 구현 완료",
        "realtime-dev": "WebSocket/SSE · 실시간 가격 피드 구현 완료",
        "infra-dev": "CI/CD · 이메일 브리핑 시스템 구축 완료",
        "performance": "Core Web Vitals · Market API 30초→3초 최적화",
        "security": "OWASP · P1 보안 이슈 4건 수정 완료",
        "qa": "Playwright E2E 27/28 PASS · 버그 15건 탐지",
        "code-janitor": "코드 정리 총괄 · 10파일 점검 완료",
        "import-police": "import 순서/미사용 감시",
        "dead-code-hunter": "죽은 코드 탐지/제거",
        "style-enforcer": "네이밍/포맷팅 일관성",
        "architecture-guard": "파일 위치/레이어 분리 감시",
        "file-organizer": "폴더 구조/중복 파일 관리",
        "finance": "₩100만 예산 추적 · 유닛 이코노믹스",
        "ir": "투자자 리포트 · 피치덱 관리",
        "revenue-ops": "결제/구독 관리 · MRR 추적",
        "product": "PRD · 기능 스펙 · 백로그 관리",
        "design": "UI/UX · 디자인 시스템 (리서치 대기중)",
        "onboarding": "투자성향 8문항 · Q6 추가+다크테마 수정 완료",
        "i18n": "영어/한국어 다국어 지원",
        "marketing": "카피 · SEO · 채널 전략",
        "growth": "A/B 테스트 · 퍼널 · 바이럴",
        "customer": "유저 피드백 · NPS · 이탈 방지",
        "competitive-intel": "경쟁사 모니터링 · 기능 비교",
        "legal": "이용약관+개인정보처리방침 초안 완료",
        "compliance-ai": "자동 금융 규제 체크 · 문구 검증",
        "analytics": "KPI 추적 · 데이터 분석",
        "quant": "15+ Factor 모델 · AdaptiveParams 3-Layer",
        "operations": "일일 운영 체크 · SLA 모니터링",
        "hr": "채용 로드맵 · 프리랜서 관리",
        "docs": "API 문서 · 아키텍처 기록",
        "strategy": "로드맵 · Phase 1→2→3 관리",
        "pitch": "면접/투자자 피치 준비",
        "audit": "Goldman 검수 · CONDITIONAL→PASS",
        "user-tester": "E2E 유저 시나리오 테스트",
        "engineering": "CTO 직속 · 기술 결정 · 코드 리뷰",
    }

    org_html = ""
    for emoji_title, role, members in org:
        active = [m for m in members if m in dept_names]
        member_lines = ""
        for m in active:
            desc = dept_desc.get(m, "")
            member_lines += (
                f'<div style="display:flex;justify-content:space-between;padding:2px 0;">'
                f'<span style="color:#e5e7eb;font-family:monospace;font-size:11px;">{m}</span>'
                f'<span style="color:#6b7280;font-size:11px;">{desc}</span>'
                f'</div>'
            )
        org_html += (
            f'<div style="margin:8px 0;padding:10px 12px;background:#0a0a0f;border-radius:6px;border-left:3px solid #10b981;">'
            f'<div style="font-size:13px;font-weight:700;color:#f3f4f6;margin-bottom:6px;">{emoji_title} <span style="font-weight:400;color:#6b7280;">({role}) — {len(active)}개 부서</span></div>'
            f'{member_lines}'
            f'</div>'
        )
    ceo_active = [m for m in ceo_direct if m in dept_names]
    ceo_lines = ""
    for m in ceo_active:
        desc = dept_desc.get(m, "")
        ceo_lines += (
            f'<div style="display:flex;justify-content:space-between;padding:2px 0;">'
            f'<span style="color:#e5e7eb;font-family:monospace;font-size:11px;">{m}</span>'
            f'<span style="color:#6b7280;font-size:11px;">{desc}</span>'
            f'</div>'
        )
    org_html += (
        f'<div style="margin:8px 0;padding:10px 12px;background:#0a0a0f;border-radius:6px;border-left:3px solid #eab308;">'
        f'<div style="font-size:13px;font-weight:700;color:#f3f4f6;margin-bottom:6px;">👤 CEO 직속 — {len(ceo_active)}개 부서</div>'
        f'{ceo_lines}'
        f'</div>'
    )
    s2 = section("🏢", f"조직도 ({n_agents} departments · {n_skills} skills)", org_html)

    # Section 3: New department ideas
    ideas = random.sample(NEW_DEPT_IDEAS, min(2, len(NEW_DEPT_IDEAS)))
    ideas_html = "".join(
        f'<p style="margin:6px 0;"><strong style="color:#10b981;">{name}</strong>: {desc}</p>'
        for name, desc in ideas
    )
    s3 = section("🆕", "신규 부서 제안", ideas_html)

    # Section 4: Claude Code tip
    tip = random.choice(CLAUDE_CODE_TIPS)
    s4 = section("🔧", f"Claude Code 활용 팁 — {tip['title']}", f"<p style='margin:0;'>{tip['body']}</p>")

    # Section 5: Business ideas
    biz = random.sample(BIZ_IDEAS, min(2, len(BIZ_IDEAS)))
    s5 = section("💡", "비즈니스 영감 아이디어", bullet_list(biz))

    return html_wrapper(
        f"Morning Briefing — {now.strftime('%Y-%m-%d')}",
        s1 + s2 + s3 + s4 + s5,
        now,
    )


def build_noon(now: datetime) -> str:
    depts = collect_departments()
    commits = git_log(3)
    n_depts = len(depts)
    n_skills = count_skills()

    # Section 1: Morning progress
    s1 = section("🕛", "오전 진행상황", (
        f'<p style="margin:0 0 8px;color:#9ca3af;">Recent git activity:</p>'
        f'{code_block(commits)}'
    ))

    # Section 2: Org update
    s2 = section("🏢", f"조직도 업데이트 ({n_depts} departments, {n_skills} skills)", (
        f'<p style="margin:0;">현재 {n_depts}개 부서 운영 중, {n_skills}개 스킬 활성화 상태입니다.</p>'
    ))

    # Section 3: Afternoon priorities
    priorities = [
        "기능 개발 또는 버그 수정 — 가장 임팩트 높은 이슈 먼저",
        "테스트/QA — 오전에 작성한 코드의 테스트 커버리지 확보",
        "문서 업데이트 — 변경사항 반영 및 README 최신화",
    ]
    s3 = section("🔥", "오후 우선순위 Top 3", bullet_list(
        [f"<strong>{i+1}.</strong> {p}" for i, p in enumerate(priorities)]
    ))

    # Section 4: Afternoon ideas
    biz = random.sample(BIZ_IDEAS, min(2, len(BIZ_IDEAS)))
    s4 = section("💡", "오후 영감 아이디어", bullet_list(biz))

    return html_wrapper(
        f"Noon Briefing — {now.strftime('%Y-%m-%d')}",
        s1 + s2 + s3 + s4,
        now,
    )


def build_evening(now: datetime) -> str:
    depts = collect_departments()
    today_commits = git_log_today()
    build_status = check_build()
    n_agents = count_agents()
    n_skills = count_skills()

    # Section 1: Today's achievements
    s1 = section("🌙", f"오늘 하루 성과 ({len(today_commits)} commits)", code_block(today_commits))

    # Section 2: Full org chart
    rows = []
    for d in depts:
        status = "Active" if d["has_skill"] else "Agent Only"
        color = "#10b981" if d["has_skill"] else "#6b7280"
        rows.append([
            d["name"],
            f'<span style="color:{color};">{status}</span>',
            "1" if d["has_skill"] else "0",
        ])
    s2 = section("🏢", f"조직도 최종 현황 ({len(depts)} departments)", make_table(
        ["Department", "Status", "Skills"], rows
    ))

    # Section 3: Tomorrow's top 5
    tomorrow_tasks = [
        "가장 중요한 미완성 기능 1개 완료하기",
        "유저 피드백 중 가장 빈번한 이슈 1개 해결",
        "테스트 커버리지 5% 이상 증가시키기",
        "기술 부채 1건 이상 해소 (리팩토링/정리)",
        "문서 또는 디자인 시스템 1건 업데이트",
    ]
    s3 = section("📌", "내일 할 일 Top 5", bullet_list(
        [f"<strong>{i+1}.</strong> {t}" for i, t in enumerate(tomorrow_tasks)]
    ))

    # Section 4: Daily dashboard
    build_color = "#10b981" if build_status == "PASS" else "#ef4444"
    build_emoji = "PASS" if build_status == "PASS" else "FAIL"
    s4 = section("📊", "일일 대시보드", (
        f'{stat_card("Departments", str(len(depts)))}'
        f'{stat_card("Skills", str(n_skills))}'
        f'{stat_card("Build", build_emoji, build_color)}'
        f'{stat_card("Today Commits", str(len(today_commits)))}'
        f'{stat_card("Agent Files", str(n_agents))}'
    ))

    # Section 5: Evening ideas
    biz = random.sample(BIZ_IDEAS, min(2, len(BIZ_IDEAS)))
    s5 = section("💡", "저녁 영감 아이디어", bullet_list(biz))

    return html_wrapper(
        f"Evening Briefing — {now.strftime('%Y-%m-%d')}",
        s1 + s2 + s3 + s4 + s5,
        now,
    )


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------

def send_email(subject: str, html_content: str) -> None:
    api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
    to_email = os.environ.get("CEO_EMAIL", "seanbae1521@gmail.com").strip()
    from_email = os.environ.get("FROM_EMAIL", "seanbae1521@gmail.com").strip()

    if not api_key or api_key == "***" or len(api_key) < 10:
        print("=" * 60)
        print("SENDGRID_API_KEY not set — printing email to stdout")
        print("=" * 60)
        print(f"TO:      {to_email}")
        print(f"FROM:    {from_email}")
        print(f"SUBJECT: {subject}")
        print("-" * 60)
        print(html_content)
        print("=" * 60)
        return

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content

    message = Mail(
        from_email=Email(from_email, "StockPilot Briefing"),
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", html_content),
    )

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        print(f"Email sent! Status: {response.status_code}")
    except Exception as e:
        print(f"Failed to send email: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

BRIEFING_TYPES = {
    "morning": ("Morning", build_morning),
    "noon": ("Noon", build_noon),
    "evening": ("Evening", build_evening),
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in BRIEFING_TYPES:
        print(f"Usage: {sys.argv[0]} morning|noon|evening")
        sys.exit(1)

    briefing_type = sys.argv[1]
    label, builder = BRIEFING_TYPES[briefing_type]

    now = datetime.now(KST)
    html = builder(now)
    subject = f"[StockPilot] {label} Briefing — {now.strftime('%Y-%m-%d')}"

    send_email(subject, html)


if __name__ == "__main__":
    main()
