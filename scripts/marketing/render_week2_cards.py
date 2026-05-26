"""
PivoxQuant D8~D14 Instagram Card Renderer
-----------------------------------------
출력: docs/marketing/week2-cards/*.png
해상도:
  - 단일 카드: 1080×1350 (4:5 세로형) for D8, D10, D13
  - 캐러셀 카드: 1080×1080 (1:1) for D9, D11, D14
  - 릴스 커버: 1080×1920 (9:16) for D12

색상 토큰 (design v3 락-인):
  INK     = #050505  Vantablack
  BRONZE  = #B8956A
  IVORY   = #F5F0E8
  IVORY_D = rgba(245,240,232,0.65)  dim
  UP      = #D18888  carmine (KR 상승)
  DOWN    = #7AA0C8  indigo  (KR 하락)

§101 준수:
  - 권유어(사세요/매수/매도/추천/목표가) 0건
  - D8 전체 수익률 1개만 (더미) + 4요소 병기 필수
  - 특정 종목명+수익률 동시 노출 금지
  - 더미/비식별 데이터만
"""

from __future__ import annotations
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── 경로 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "marketing" / "week2-cards"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 폰트 경로 (시스템 TTF, 1주차 동일 경로) ──────────────────────────────────
_PLAYFAIR   = "/Users/seanbae/Library/Fonts/PlayfairDisplay[wght].ttf"
_JETBRAINS  = "/Users/seanbae/Library/Fonts/JetBrainsMono-Regular.ttf"
_JETBRAINS_B= "/Users/seanbae/Library/Fonts/JetBrainsMono-Bold.ttf"
_KR_SANS    = "/System/Library/Fonts/AppleSDGothicNeo.ttc"  # 한글 본문

# ── 색상 토큰 ─────────────────────────────────────────────────────────────────
INK         = (5,   5,   5)
BRONZE      = (184, 149, 106)
BRONZE_DIM  = (184, 149, 106, 140)
IVORY       = (245, 240, 232)
IVORY_D     = (245, 240, 232, 166)   # 0.65
IVORY_MID   = (245, 240, 232, 140)   # 0.55
IVORY_FAINT = (245, 240, 232, 100)   # ~0.39
HAIRLINE    = (245, 240, 232, 20)    # 0.08 hairline
DIVIDER     = (184, 149, 106, 60)    # bronze hairline

# ── 폰트 로더 ─────────────────────────────────────────────────────────────────
def _f(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)

# ── 기본 캔버스 ───────────────────────────────────────────────────────────────
def make_canvas(w: int = 1080, h: int = 1080) -> tuple[Image.Image, ImageDraw.Draw]:
    img = Image.new("RGBA", (w, h), INK + (255,))
    return img, ImageDraw.Draw(img, "RGBA")

# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────
def draw_brand_mark(draw: ImageDraw.Draw, w: int, y_bottom: int):
    """하단 브랜드마크 + 면책 한 줄 — 줄 없이 텍스트만"""
    font_brand = _f(_JETBRAINS_B, 18)
    font_disc  = _f(_KR_SANS,     16)
    draw.text((w // 2, y_bottom - 48), "PIVOXQUANT",
              font=font_brand, fill=BRONZE + (160,), anchor="mm")
    draw.text((w // 2, y_bottom - 26),
              "정보 제공 도구 · 투자자문 아님",
              font=font_disc, fill=IVORY_FAINT, anchor="mm")

def draw_top_bar(draw: ImageDraw.Draw, w: int):
    """상단 bar — 제거됨 (CEO 지적: 붕 떠보임). no-op 유지."""
    pass

def draw_bottom_bar(draw: ImageDraw.Draw, w: int, h: int):
    """하단 bar — 제거됨 (CEO 지적: 푸터 과도한 줄). no-op 유지."""
    pass

def draw_slide_num(draw: ImageDraw.Draw, w: int, num: str):
    """우상단 슬라이드 번호"""
    f = _f(_JETBRAINS, 22)
    draw.text((w - 70, 70), num, font=f, fill=BRONZE + (160,), anchor="rm")

def wrap_text(text: str, font: ImageFont.FreeTypeFont,
              max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """단순 줄바꿈 (공백 기준)"""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def draw_wrapped(draw: ImageDraw.Draw, text: str,
                 font: ImageFont.FreeTypeFont,
                 x: int, y: int, max_width: int,
                 fill, line_height: int,
                 anchor: str = "lm") -> int:
    """여러 줄 텍스트 그리기, 마지막 줄 y 반환"""
    lines = wrap_text(text, font, max_width, draw)
    cy = y
    for line in lines:
        draw.text((x, cy), line, font=font, fill=fill, anchor=anchor)
        cy += line_height
    return cy


# ═══════════════════════════════════════════════════════════════════════════════
# D8 · 단일 카드 1080×1350 (4:5 세로형) — Brag Card
# §101: 전체 수익률 더미 1개 + 4요소 동일 화면 병기 필수
# 특정 종목명+수익률 동시 노출 금지
# ═══════════════════════════════════════════════════════════════════════════════
def render_d8():
    W, H = 1080, 1350
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)

    f_eye    = _f(_JETBRAINS_B, 22)
    f_play   = _f(_PLAYFAIR, 52)    # 영문 헤딩 — Playfair
    f_head   = _f(_KR_SANS, 52)     # 한글 헤드라인 — KR
    f_mono   = _f(_JETBRAINS_B, 88) # 수익률 숫자 — JetBrains
    f_sub    = _f(_KR_SANS, 30)
    f_disc   = _f(_KR_SANS, 20)     # 4요소 면책
    f_disc_s = _f(_KR_SANS, 18)

    # Eyebrow
    draw.text((90, 120), "D8 · BRAG CARD", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 상단 Playfair 영문 헤딩
    draw.text((W // 2, 195), "Monthly Brag Card",
              font=f_play, fill=IVORY, anchor="mm")

    # 서브 타이틀
    draw.text((W // 2, 285), "이번 달, 내 포트폴리오 한 장",
              font=f_head, fill=IVORY_D, anchor="mm")

    # Bronze 좌측 바
    draw.rectangle([60, 370, 65, 680], fill=BRONZE + (50,))

    # 포트폴리오 전체 수익률 더미 (전체 수치 1개만, §101)
    draw.text((W // 2, 440), "포트폴리오 전체",
              font=_f(_KR_SANS, 28), fill=IVORY_FAINT, anchor="mm")

    # 수익률 숫자 — JetBrains Mono Bronze (더미)
    draw.text((W // 2, 560), "+7.34%",
              font=f_mono, fill=BRONZE, anchor="mm")

    # "더미 데이터" 라벨 (오탐 방지)
    draw.rectangle([340, 610, 740, 645], fill=(184, 149, 106, 40))
    draw.text((W // 2, 628), "더미 데이터 · 실제 수치 아님",
              font=_f(_JETBRAINS_B, 18), fill=BRONZE + (160,), anchor="mm")

    # 포트폴리오 구성 안내 (비식별, 종목명 금지)
    draw.text((W // 2, 720), "종목 A · 종목 B · 종목 C · 종목 D",
              font=f_sub, fill=IVORY_MID, anchor="mm")
    draw.text((W // 2, 762), "비식별 처리 · 특정 종목명 미표기",
              font=_f(_KR_SANS, 24), fill=IVORY_FAINT, anchor="mm")

    # ── 4요소 병기 (§101 필수) ────────────────────────────────────────────────
    # 영역 박스
    draw.rectangle([80, 820, W - 80, 1080], fill=(184, 149, 106, 8))
    draw.rectangle([80, 820, W - 80, 1080], outline=BRONZE + (50,), width=1)

    # ① 측정 기간
    draw.text((120, 855), "①",
              font=_f(_KR_SANS, 22), fill=BRONZE, anchor="lm")
    draw.text((160, 855), "측정 기간: 2026-05-01 ~ 2026-05-31",
              font=f_disc, fill=IVORY_D, anchor="lm")

    # ② 면책
    draw.text((120, 905), "②",
              font=_f(_KR_SANS, 22), fill=BRONZE, anchor="lm")
    draw.text((160, 905), "과거 성과는 미래 수익을 보장하지 않습니다.",
              font=f_disc, fill=IVORY_D, anchor="lm")

    # ③ 개별 사례
    draw.text((120, 955), "③",
              font=_f(_KR_SANS, 22), fill=BRONZE, anchor="lm")
    draw.text((160, 955), "개별 이용자 사례이며 전체를 대표하지 않습니다.",
              font=f_disc, fill=IVORY_D, anchor="lm")

    # ④ AI 생성 라벨
    draw.text((120, 1005), "④",
              font=_f(_KR_SANS, 22), fill=BRONZE, anchor="lm")
    draw.text((160, 1005), "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=f_disc, fill=IVORY_D, anchor="lm")

    # 투자 판단 책임 한 줄
    draw.text((W // 2, 1065), "투자 판단과 책임은 이용자 본인에게 있습니다.",
              font=f_disc_s, fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)

    out = OUT_DIR / "d8_brag_card.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D8 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D9 슬라이드 1 · 표지 — 모닝 브리핑 해부
# ═══════════════════════════════════════════════════════════════════════════════
def render_d9_slide1():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "1 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 66)
    f_sub  = _f(_KR_SANS, 34)
    f_mono = _f(_JETBRAINS_B, 30)

    draw.text((90, 130), "D9 · MORNING BRIEF", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 메인 헤드라인
    draw.text((W // 2, 290), "모닝 브리핑 한 장,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 375), "분해해 봤습니다.",
              font=f_head, fill=BRONZE, anchor="mm")

    # 서브
    draw.text((W // 2, 510), "구성 요소 4가지",
              font=_f(_KR_SANS, 30), fill=IVORY_D, anchor="mm")

    # 4요소 리스트
    f_item = _f(_KR_SANS, 32)
    f_desc = _f(_KR_SANS, 26)
    items = [
        ("①", "어젯밤 미국장 요약",    "내 종목 기준 밤사이 움직임"),
        ("②", "내 종목 뉴스 흐름",    "포트폴리오에 걸리는 것만"),
        ("③", "다가오는 실적 일정",    "내가 가진 종목 중 곧 발표"),
        ("④", "그날의 관찰 포인트",    "체크 항목 — 판단은 당신이"),
    ]
    y = 570
    for num, title, desc in items:
        draw.text((130, y), num, font=_f(_KR_SANS, 28), fill=BRONZE, anchor="lm")
        draw.text((185, y), title, font=f_item, fill=IVORY, anchor="lm")
        draw.text((185, y + 36), desc, font=f_desc, fill=IVORY_FAINT, anchor="lm")
        y += 90

    # 스와이프 힌트
    draw.text((W // 2, 930), "스와이프 →",
              font=_f(_KR_SANS, 26), fill=BRONZE + (140,), anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d9_slide1_cover.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D9-1 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D9 슬라이드 2 · 자리표시 (캡처 대체용)
# ═══════════════════════════════════════════════════════════════════════════════
def render_d9_slide2_placeholder():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "2 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_note = _f(_KR_SANS, 36)
    f_sub  = _f(_KR_SANS, 28)
    f_tag  = _f(_JETBRAINS_B, 24)

    draw.text((90, 130), "D9 · MORNING BRIEF", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 점선 영역 (캡처 대체)
    for y in range(200, 870, 18):
        draw.rectangle([120, y, W - 120, y + 1], fill=HAIRLINE)
    draw.rectangle([120, 200, W - 120, 870], outline=BRONZE + (60,), width=2)

    draw.text((W // 2, 480), "[ ① 미국장 요약 + ② 뉴스 흐름 캡처 ]",
              font=f_note, fill=BRONZE + (140,), anchor="mm")
    draw.text((W // 2, 540), "CEO 캡처 삽입 위치",
              font=f_sub, fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 590), "개인정보 · 종목+수익률 동시 노출 금지",
              font=f_sub, fill=IVORY_FAINT, anchor="mm")

    # AI 생성 라벨
    draw.rectangle([120, 200, 310, 248], fill=BRONZE + (200,))
    draw.text((215, 224), "AI 생성",
              font=_f(_KR_SANS, 24), fill=INK + (255,), anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d9_slide2_placeholder.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D9-2 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D9 슬라이드 3 · 실적 일정 + 뉴스 텍스트 카드
# ═══════════════════════════════════════════════════════════════════════════════
def render_d9_slide3():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "3 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 52)
    f_sub  = _f(_KR_SANS, 30)
    f_body = _f(_KR_SANS, 28)
    f_mono = _f(_JETBRAINS, 26)

    draw.text((90, 130), "D9 · BRIEF CONTENTS", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # ② 뉴스 + ③ 실적 일정 설명
    draw.text((W // 2, 235), "② 내 종목 뉴스 · ③ 실적 일정",
              font=f_head, fill=IVORY, anchor="mm")

    # ② 뉴스 박스
    draw.rectangle([80, 295, W - 80, 555], fill=(184, 149, 106, 10))
    draw.rectangle([80, 295, W - 80, 555], outline=BRONZE + (50,), width=1)
    draw.text((120, 325), "② 내 종목에 걸리는 뉴스만",
              font=f_sub, fill=BRONZE, anchor="lm")
    news_lines = [
        "시장 전체 뉴스가 아니라,",
        "내 포트폴리오 종목에",
        "실제로 걸리는 것만 정리합니다.",
    ]
    y = 385
    for line in news_lines:
        draw.text((120, y), line, font=f_body, fill=IVORY_D, anchor="lm")
        y += 48

    # ③ 실적 박스
    draw.rectangle([80, 575, W - 80, 800], fill=(184, 149, 106, 10))
    draw.rectangle([80, 575, W - 80, 800], outline=BRONZE + (50,), width=1)
    draw.text((120, 605), "③ 다가오는 실적 일정",
              font=f_sub, fill=BRONZE, anchor="lm")

    # 더미 실적 일정
    dummy_sched = [
        ("종목 A",  "D+3"),
        ("종목 B",  "D+7"),
    ]
    y = 665
    for ticker, when in dummy_sched:
        draw.text((120, y), ticker, font=_f(_KR_SANS, 26), fill=IVORY, anchor="lm")
        draw.text((500, y), when,   font=f_mono, fill=BRONZE, anchor="lm")
        y += 54

    draw.text((120, 760), "더미 데이터 · 종목명 비식별",
              font=_f(_KR_SANS, 18), fill=IVORY_FAINT, anchor="lm")

    draw.text((W // 2, 870),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 24), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d9_slide3_news_earnings.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D9-3 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D9 슬라이드 4 · 관찰 포인트 — "판단은 당신이"
# ═══════════════════════════════════════════════════════════════════════════════
def render_d9_slide4():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "4 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 60)
    f_sub  = _f(_KR_SANS, 32)
    f_body = _f(_KR_SANS, 28)

    draw.text((90, 130), "D9 · OBSERVATION POINT", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    # Bronze 좌측 바
    draw.rectangle([80, 250, 86, 540], fill=BRONZE)

    draw.text((W // 2, 295), "④ 그날의 관찰 포인트",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 370), "— 판단은 당신이.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 500), "단정이 아니라,",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 548), "\"이런 것들 한 번 보세요\" 수준의 체크 항목.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    draw.text((W // 2, 650), "차트 앱 다섯 개 켜고",
              font=f_body, fill=IVORY_MID, anchor="mm")
    draw.text((W // 2, 698), "손으로 모으던 걸,",
              font=f_body, fill=IVORY_MID, anchor="mm")
    draw.text((W // 2, 746), "자는 동안 대신 정리해 둡니다.",
              font=f_body, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 856),
              "정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 24), fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 894),
              "과거 성과는 미래 수익을 보장하지 않습니다.",
              font=_f(_KR_SANS, 22), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d9_slide4_observation.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D9-4 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D10 · 단일 카드 1080×1350 (4:5) — "묻지 않아도 먼저 옵니다"
# ═══════════════════════════════════════════════════════════════════════════════
def render_d10():
    W, H = 1080, 1350
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 72)
    f_sub  = _f(_KR_SANS, 34)
    f_body = _f(_KR_SANS, 30)
    f_disc = _f(_KR_SANS, 22)

    draw.text((90, 120), "D10 · PROACTIVE", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 브론즈 수직 액센트 라인
    draw.rectangle([60, 170, 63, H - 170], fill=BRONZE + (30,))

    # 메인 헤드라인 (대형)
    draw.text((W // 2, 270), "묻지 않아도,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 360), "먼저 옵니다.",
              font=f_head, fill=BRONZE, anchor="mm")

    # 서브 카피
    draw.text((W // 2, 490),
              "질문하는 도구가 아니라,",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 540),
              "먼저 정리해 두는 도구",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # ── 대화형 vs PivoxQuant 비교 (좌우 정렬 통일) ──
    # 공통 패널 상단 y
    PANEL_TOP  = 625
    PANEL_BOT  = 830
    MID        = W // 2
    LEFT_CX    = (80 + MID - 20) // 2         # 좌 패널 중앙 x
    RIGHT_CX   = MID + 20 + (W - 80 - MID - 20) // 2  # 우 패널 중앙 x

    # 좌 패널 — 대화형 AI
    draw.rectangle([80, PANEL_TOP, MID - 20, PANEL_BOT],
                   fill=(20, 20, 20, 255))
    draw.rectangle([80, PANEL_TOP, MID - 20, PANEL_BOT],
                   outline=(245, 240, 232, 30), width=1)
    # 좌 제목 (패널 상단 + 40px)
    TITLE_Y    = PANEL_TOP + 46
    BULLET_Y1  = TITLE_Y + 60
    BULLET_Y2  = BULLET_Y1 + 42
    draw.text((LEFT_CX, TITLE_Y), "대화형 AI",
              font=_f(_KR_SANS, 30), fill=IVORY_MID, anchor="mm")
    draw.text((LEFT_CX, BULLET_Y1), "내가 매번 물어야",
              font=_f(_KR_SANS, 26), fill=IVORY_MID, anchor="mm")
    draw.text((LEFT_CX, BULLET_Y2), "답이 나온다",
              font=_f(_KR_SANS, 26), fill=IVORY_MID, anchor="mm")

    # 우 패널 — PivoxQuant (동일 y 기준)
    draw.rectangle([MID + 20, PANEL_TOP, W - 80, PANEL_BOT],
                   fill=(184, 149, 106, 18))
    draw.rectangle([MID + 20, PANEL_TOP, W - 80, PANEL_BOT],
                   outline=BRONZE + (60,), width=1)
    # 우 제목 (TITLE_Y와 동일) — bronze 배경 위라 Vantablack으로 가독성 확보
    draw.text((RIGHT_CX, TITLE_Y), "PivoxQuant",
              font=_f(_JETBRAINS_B, 26), fill=INK + (255,), anchor="mm")
    # 우 불릿 (BULLET_Y1/Y2와 동일)
    draw.text((RIGHT_CX, BULLET_Y1), "정해진 시각에",
              font=_f(_KR_SANS, 26), fill=IVORY, anchor="mm")
    draw.text((RIGHT_CX, BULLET_Y2), "먼저 도착",
              font=_f(_KR_SANS, 26), fill=IVORY, anchor="mm")

    # 시각 강조 — 이모지 없이 텍스트만 (KR_SANS: 한글 포함, 숫자/→ 도 렌더 가능)
    draw.text((W // 2, 910), "06:00  →  메일함 도착",
              font=_f(_KR_SANS, 34), fill=BRONZE, anchor="mm")
    draw.text((W // 2, 960),
              "질문하기 전에, 이미 정리가 끝나 있습니다.",
              font=f_body, fill=IVORY_D, anchor="mm")

    # 면책 (하단)
    draw.text((W // 2, 1050),
              "물론 무엇을 하라고 정해주진 않습니다.",
              font=f_disc, fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 1080), "판단은 늘 당신 몫이에요.",
              font=f_disc, fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 1118),
              "정보 제공 도구 · 투자자문 아님",
              font=f_disc, fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d10_proactive_card.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D10 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D11 슬라이드 1 · 표지 — 실적 캘린더
# ═══════════════════════════════════════════════════════════════════════════════
def render_d11_slide1():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "1 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 62)
    f_sub  = _f(_KR_SANS, 32)

    draw.text((90, 130), "D11 · EARNINGS CALENDAR", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 295), "내 종목 실적 일정만,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 378), "따로 모아드립니다.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 514),
              "시장 전체 캘린더가 아니라,",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 562),
              "\"내 포트폴리오에 걸리는 일정\"만.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # 안내 포인트
    f_item = _f(_KR_SANS, 28)
    points = [
        "발표 다가오는 종목 자동 필터",
        "과거 실적 추이 미리 정리",
        "컨센서스 데이터 공식 출처만",
        "예측 아님 — 발표를 더 잘 읽도록",
    ]
    y = 660
    for pt in points:
        draw.rectangle([130, y - 8, 138, y + 8], fill=BRONZE)
        draw.text((160, y), pt, font=f_item, fill=IVORY_MID, anchor="lm")
        y += 56

    draw.text((W // 2, 950), "스와이프 →",
              font=_f(_KR_SANS, 26), fill=BRONZE + (140,), anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d11_slide1_cover.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D11-1 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D11 슬라이드 2 · 자리표시 (캘린더 캡처 대체)
# ═══════════════════════════════════════════════════════════════════════════════
def render_d11_slide2_placeholder():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "2 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_note = _f(_KR_SANS, 34)
    f_sub  = _f(_KR_SANS, 26)
    f_tag  = _f(_JETBRAINS_B, 22)

    draw.text((90, 130), "D11 · EARNINGS CALENDAR", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    # 캘린더 목업 그리드
    draw.rectangle([80, 200, W - 80, 870], outline=BRONZE + (60,), width=2)

    # 헤더
    draw.rectangle([80, 200, W - 80, 250], fill=BRONZE + (30,))
    draw.text((W // 2, 225), "내 포트폴리오 실적 일정",
              font=f_note, fill=IVORY, anchor="mm")

    # 더미 캘린더 그리드 (종목명 단독 OK, 등락 라벨 금지)
    days = ["월", "화", "수", "목", "금"]
    col_w = (W - 80 - 80) // 5
    for i, day in enumerate(days):
        cx = 80 + col_w * i + col_w // 2
        draw.text((cx, 290), day, font=_f(_KR_SANS, 22), fill=BRONZE, anchor="mm")
        draw.rectangle([80 + col_w * i, 305, 80 + col_w * (i + 1) - 4, 306],
                       fill=HAIRLINE)

    # 더미 행 (종목명만, 등락/수익 라벨 없음)
    cal_rows = [
        ["",        "종목 A", "",      "종목 B", ""      ],
        ["종목 C",  "",       "",      "",       "종목 D" ],
    ]
    y_row = 340
    for row in cal_rows:
        for i, cell in enumerate(row):
            if cell:
                cx = 80 + col_w * i + col_w // 2
                draw.rectangle([80 + col_w * i + 4, y_row - 24,
                                 80 + col_w * (i + 1) - 8, y_row + 28],
                                fill=(184, 149, 106, 15))
                draw.text((cx, y_row), cell, font=_f(_KR_SANS, 24),
                          fill=IVORY, anchor="mm")
        y_row += 76

    draw.text((W // 2, 600), "[ CEO 실제 캘린더 캡처 삽입 ]",
              font=f_note, fill=BRONZE + (120,), anchor="mm")
    draw.text((W // 2, 650), "종목명 단독 OK · 등락 라벨 금지",
              font=f_sub, fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 700), "개인정보 · 특정 수익률 노출 금지",
              font=f_sub, fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d11_slide2_placeholder.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D11-2 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D11 슬라이드 3 · 발표 전 데이터 더미 카드
# 종목명 비식별 처리 + 등락 라벨 없음
# ═══════════════════════════════════════════════════════════════════════════════
def render_d11_slide3():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "3 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 52)
    f_sub  = _f(_KR_SANS, 30)
    f_mono = _f(_JETBRAINS, 24)
    f_tag  = _f(_JETBRAINS_B, 20)

    draw.text((90, 130), "D11 · PRE-BRIEF DATA", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 220), "발표 전, 데이터 먼저.",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 282), "과거 추이 · 컨센서스",
              font=f_sub, fill=BRONZE, anchor="mm")

    # 더미 과거 실적 추이 박스 (종목명 비식별, 등락 수치 없음)
    draw.rectangle([80, 344, W - 80, 620],
                   fill=(184, 149, 106, 8))
    draw.rectangle([80, 344, W - 80, 620],
                   outline=BRONZE + (50,), width=1)

    draw.rectangle([80, 344, W - 80, 384], fill=BRONZE + (28,))
    cols = ["분기", "구분 A", "구분 B", "컨센서스"]
    col_x = [130, 340, 570, 790]
    for cx, col in zip(col_x, cols):
        draw.text((cx, 364), col, font=_f(_KR_SANS, 20), fill=BRONZE, anchor="lm")

    rows_dummy = [
        ("Q1", "—", "—", "—"),
        ("Q2", "—", "—", "—"),
        ("Q3", "—", "—", "—"),
    ]
    y = 410
    for row in rows_dummy:
        for cx, cell in zip(col_x, row):
            draw.text((cx, y), cell, font=f_mono, fill=IVORY_MID, anchor="lm")
        y += 60
        draw.rectangle([100, y - 18, W - 100, y - 17], fill=HAIRLINE)

    draw.text((W // 2, 604), "더미 데이터 · 종목명 비식별 · 수익률 미표기",
              font=_f(_KR_SANS, 20), fill=BRONZE + (130,), anchor="mm")

    # 안내 메시지
    draw.text((W // 2, 700),
              "\"좋을 것 / 나쁠 것\"을 정해주는 게 아니에요.",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 750),
              "발표를 더 잘 읽도록 자료를 먼저 깔아두는 쪽.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    draw.text((W // 2, 852),
              "컨센서스 출처: 공식 라이선스 데이터만",
              font=_f(_KR_SANS, 26), fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 892),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 24), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d11_slide3_prebrief.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D11-3 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D11 슬라이드 4 · "예측이 아니라, 판단은 당신이"
# ═══════════════════════════════════════════════════════════════════════════════
def render_d11_slide4():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "4 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 62)
    f_sub  = _f(_KR_SANS, 32)

    draw.text((90, 130), "D11 · JUDGMENT", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    draw.rectangle([80, 248, 88, 600], fill=BRONZE)

    draw.text((W // 2, 295), "예측이 아니라,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 378), "발표를 더 잘 읽도록.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 518), "판단은 당신이.",
              font=f_head, fill=IVORY, anchor="mm")

    draw.text((W // 2, 660),
              "내가 등록한 포트폴리오 종목 기준으로",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 710),
              "실적 일정과 자료를 먼저 정리해 둡니다.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    draw.text((W // 2, 830),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 26), fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 870),
              "과거 성과는 미래 수익을 보장하지 않습니다.",
              font=_f(_KR_SANS, 24), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d11_slide4_judgment.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D11-4 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D12 · 릴스 커버 1080×1920 (9:16) + 자막 스펙
# ═══════════════════════════════════════════════════════════════════════════════
def render_d12_reels_cover():
    W, H = 1080, 1920
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)

    f_eye  = _f(_JETBRAINS_B, 26)
    f_head = _f(_KR_SANS, 80)
    f_sub  = _f(_KR_SANS, 40)
    f_body = _f(_KR_SANS, 32)
    f_tag  = _f(_JETBRAINS_B, 28)

    draw.text((90, 140), "D12 · REELS COVER", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    # AI 생성 태그 (좌상단 — 첫 3초 안에 노출, §101)
    draw.rectangle([80, 190, 380, 244], fill=BRONZE + (200,))
    draw.text((230, 217), "AI 생성 콘텐츠 포함",
              font=_f(_KR_SANS, 26), fill=INK + (255,), anchor="mm")

    # 정보 제공 도구 라벨
    draw.rectangle([80, 254, 380, 300], fill=(184, 149, 106, 60))
    draw.text((230, 277), "정보 제공 도구",
              font=_f(_KR_SANS, 26), fill=IVORY, anchor="mm")

    # 메인 훅 (1인 개발자 빌딩 인 퍼블릭 2주차)
    draw.text((W // 2, 430), "1인 개발자가",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 535), "투자 도구 만드는 중",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 640), "— 2주차",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 795),
              "취준 중 개인 투자자 + 1인 개발자",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 855),
              "책상 하나에서 혼자 합니다.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # 포인트 박스
    draw.rectangle([120, 910, W - 120, 1100],
                   fill=(184, 149, 106, 10))
    draw.rectangle([120, 910, W - 120, 1100],
                   outline=BRONZE + (60,), width=2)
    draw.text((W // 2, 960),
              "왜 \"사라/팔라\" 안 하냐면",
              font=f_body, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 1010),
              "— 정보만 정리하는 쪽이니까.",
              font=f_body, fill=BRONZE, anchor="mm")
    draw.text((W // 2, 1060),
              "느리지만 과정 그대로 여기 올립니다.",
              font=f_body, fill=IVORY_D, anchor="mm")

    # 릴스 스펙 안내
    draw.text((W // 2, 1190),
              "릴스 20~30초 커버 이미지",
              font=_f(_KR_SANS, 30), fill=BRONZE + (160,), anchor="mm")
    draw.text((W // 2, 1240),
              "영상 촬영: CEO 직접",
              font=_f(_KR_SANS, 28), fill=IVORY_FAINT, anchor="mm")

    # 자막 스펙 박스
    draw.rectangle([120, 1295, W - 120, 1730],
                   fill=(18, 18, 18, 255))
    draw.rectangle([120, 1295, W - 120, 1730],
                   outline=(184, 149, 106, 60), width=1)
    draw.text((W // 2, 1335), "자막 스펙",
              font=_f(_KR_SANS, 30), fill=BRONZE, anchor="mm")

    captions = [
        ("0~3s",   '"1인 개발자 + AI 생성 콘텐츠 포함"'),
        ("3~12s",  "취준하면서 제 돈도 굴리는 개인 투자자"),
        ("12~22s", "왜 사라/팔라 안 하냐면"),
        ("      ", "— 정보만 정리하니까"),
        ("22~30s", "느리지만 과정 그대로. 피드백 환영"),
        ("끝",     "프로필 링크"),
    ]
    f_cap_t = _f(_JETBRAINS, 26)
    f_cap_c = _f(_KR_SANS, 27)
    y = 1386
    for ts, cap in captions:
        ts_has_kr = any('가' <= c <= '힣' for c in ts)
        ts_font = _f(_KR_SANS, 26) if ts_has_kr else f_cap_t
        draw.text((155, y), ts, font=ts_font, fill=BRONZE + (255,), anchor="lm")
        draw.text((345, y), cap, font=f_cap_c, fill=IVORY + (255,), anchor="lm")
        y += 58

    draw.text((W // 2, 1780),
              "정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 28), fill=IVORY_FAINT, anchor="mm")
    draw_brand_mark(draw, W, H)

    out = OUT_DIR / "d12_reels_cover.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D12 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D13 · 단일 카드 1080×1350 (4:5) — "데이터로 정리, 판단은 당신"
# ═══════════════════════════════════════════════════════════════════════════════
def render_d13():
    W, H = 1080, 1350
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 64)
    f_sub  = _f(_KR_SANS, 34)
    f_body = _f(_KR_SANS, 30)
    f_disc = _f(_KR_SANS, 22)

    draw.text((90, 120), "D13 · PHILOSOPHY", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    # 브론즈 좌측 바
    draw.rectangle([60, 180, 66, 780], fill=BRONZE + (40,))

    # 메인 헤드라인 — 미니멀, 여백 충분
    draw.text((W // 2, 260), "데이터로 정리합니다.",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 348), "판단은 당신이 합니다.",
              font=f_head, fill=BRONZE, anchor="mm")

    # 서브 카피
    draw.text((W // 2, 490),
              "고르는 도구가 아니라, 모아주는 도구",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # 2가지 약속 박스 — 텍스트에 맞게 높이 조정 (빈 공간 제거)
    # 구성: 상단패딩(24) + 제목줄(36) + 간격(20) + 첫번째항목(40) + 간격(16) + 두번째항목(40) + 하단패딩(24)
    # = 24 + 36 + 20 + 40 + 16 + 40 + 24 = 200px
    BOX2_TOP = 560
    BOX2_BOT = BOX2_TOP + 200
    draw.rectangle([80, BOX2_TOP, W - 80, BOX2_BOT],
                   fill=(184, 149, 106, 8))
    draw.rectangle([80, BOX2_TOP, W - 80, BOX2_BOT],
                   outline=BRONZE + (50,), width=1)

    draw.text((130, BOX2_TOP + 24 + 18), "PivoxQuant의 두 가지 약속",
              font=_f(_KR_SANS, 28), fill=BRONZE, anchor="lm")

    ROW1_Y = BOX2_TOP + 24 + 36 + 20 + 20  # 텍스트 중심 y
    draw.text((130, ROW1_Y), "하나.",
              font=_f(_JETBRAINS_B, 28), fill=BRONZE, anchor="lm")
    draw.text((230, ROW1_Y),
              "데이터는 공식 출처에서만.",
              font=f_body, fill=IVORY, anchor="lm")

    ROW2_Y = ROW1_Y + 56
    draw.text((130, ROW2_Y), "둘.",
              font=_f(_JETBRAINS_B, 28), fill=BRONZE, anchor="lm")
    draw.text((230, ROW2_Y),
              "무엇을 하라고 말하지 않습니다.",
              font=f_body, fill=IVORY, anchor="lm")

    # 브랜드 철학 한 줄
    draw.text((W // 2, 915),
              "그 자리는 CFO인 당신 거예요.",
              font=_f(_KR_SANS, 36), fill=IVORY, anchor="mm")

    # 하단 면책
    disc_lines = [
        "AI \"AI가 골라준다\"가 아니라 \"AI가 정리해준다\".",
        "공식 출처 데이터만 · 정보 제공 도구 · 투자자문 아님",
        "과거 성과는 미래 수익을 보장하지 않습니다.",
        "투자 판단과 책임은 이용자 본인에게 있습니다.",
    ]
    y = 1008
    for line in disc_lines:
        draw.text((W // 2, y), line, font=f_disc, fill=IVORY_FAINT, anchor="mm")
        y += 32

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d13_philosophy_card.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D13 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D14 슬라이드 1 · 표지 — 기능 총정리
# ═══════════════════════════════════════════════════════════════════════════════
def render_d14_slide1():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "1 / 5")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 68)
    f_sub  = _f(_KR_SANS, 32)

    draw.text((90, 130), "D14 · FEATURE SUMMARY", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 290), "2주, 한 번에 정리합니다.",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 375), "기능 총정리",
              font=_f(_KR_SANS, 36), fill=BRONZE, anchor="mm")

    # D8~D14 타임라인
    f_d = _f(_JETBRAINS_B, 24)
    f_t = _f(_KR_SANS, 24)
    timeline = [
        ("D8",  "Brag Card — 월별 포트폴리오 한 장"),
        ("D9",  "모닝 브리핑 해부 — 4가지 구성요소"),
        ("D10", "묻지 않아도 먼저 온다"),
        ("D11", "실적 캘린더 — 내 종목 일정만"),
        ("D12", "1인 개발자 비하인드 2"),
        ("D13", "데이터 정리 · 판단은 당신"),
        ("D14", "2주 총정리 + 베타 안내"),
    ]
    y = 475
    for d_label, desc in timeline:
        draw.ellipse([130, y - 8, 148, y + 8], fill=BRONZE)
        if d_label != "D14":
            draw.rectangle([138, y + 8, 140, y + 40], fill=BRONZE + (80,))
        draw.text((165, y), d_label, font=f_d, fill=BRONZE, anchor="lm")
        draw.text((250, y), desc, font=f_t, fill=IVORY_D, anchor="lm")
        y += 48

    draw.text((W // 2, 935), "스와이프 →",
              font=_f(_KR_SANS, 26), fill=BRONZE + (140,), anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d14_slide1_cover.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D14-1 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D14 슬라이드 2 · 기능 1+2 (모닝브리핑 + 위클리메모)
# ═══════════════════════════════════════════════════════════════════════════════
def render_d14_slide2():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "2 / 5")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_num  = _f(_JETBRAINS_B, 48)
    f_head = _f(_KR_SANS, 44)
    f_sub  = _f(_KR_SANS, 28)
    f_body = _f(_KR_SANS, 26)

    draw.text((90, 130), "D14 · FEATURES 1+2", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 기능 1 — 모닝 브리핑
    draw.rectangle([80, 190, W - 80, 490],
                   fill=(184, 149, 106, 10))
    draw.rectangle([80, 190, W - 80, 490],
                   outline=BRONZE + (70,), width=2)

    draw.text((140, 235), "①", font=f_num, fill=BRONZE, anchor="lm")
    draw.text((240, 235), "모닝 브리핑", font=f_head, fill=IVORY, anchor="lm")

    brief_items = [
        "매일 아침 6시 메일함에 도착",
        "미국장 · 내 종목 뉴스 · 실적 일정 · 관찰 포인트",
        "포트폴리오 등록 1회, 이후 자동",
    ]
    y = 306
    for item in brief_items:
        draw.text((155, y), f"· {item}", font=f_body, fill=IVORY_D, anchor="lm")
        y += 46

    # 기능 2 — 위클리 메모
    draw.rectangle([80, 510, W - 80, 810],
                   fill=(184, 149, 106, 10))
    draw.rectangle([80, 510, W - 80, 810],
                   outline=BRONZE + (70,), width=2)

    draw.text((140, 555), "②", font=f_num, fill=BRONZE, anchor="lm")
    draw.text((240, 555), "위클리 메모", font=f_head, fill=IVORY, anchor="lm")

    weekly_items = [
        "일요일, 5페이지 PDF 자동 발송",
        "한 주 포트폴리오 변동 정리",
        "포트폴리오 개요 · 시장동향 · 뉴스 · 실적 · 관찰",
    ]
    y = 626
    for item in weekly_items:
        draw.text((155, y), f"· {item}", font=f_body, fill=IVORY_D, anchor="lm")
        y += 46

    draw.text((W // 2, 875),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 24), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d14_slide2_features12.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D14-2 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D14 슬라이드 3 · 기능 3+4 (실적프리브리프 + Brag Card)
# ═══════════════════════════════════════════════════════════════════════════════
def render_d14_slide3():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "3 / 5")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_num  = _f(_JETBRAINS_B, 48)
    f_head = _f(_KR_SANS, 44)
    f_body = _f(_KR_SANS, 26)

    draw.text((90, 130), "D14 · FEATURES 3+4", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 기능 3 — 실적 프리브리프
    draw.rectangle([80, 190, W - 80, 490],
                   fill=(184, 149, 106, 10))
    draw.rectangle([80, 190, W - 80, 490],
                   outline=BRONZE + (70,), width=2)

    draw.text((140, 235), "③", font=f_num, fill=BRONZE, anchor="lm")
    draw.text((240, 235), "실적 프리브리프", font=f_head, fill=IVORY, anchor="lm")

    pref_items = [
        "내 종목 발표 전, 과거 추이 + 컨센서스",
        "종목명 비식별 · 공식 라이선스 데이터만",
        "예측 아님 — 발표를 더 잘 읽도록",
    ]
    y = 306
    for item in pref_items:
        draw.text((155, y), f"· {item}", font=f_body, fill=IVORY_D, anchor="lm")
        y += 46

    # 기능 4 — Brag Card
    draw.rectangle([80, 510, W - 80, 810],
                   fill=(184, 149, 106, 10))
    draw.rectangle([80, 510, W - 80, 810],
                   outline=BRONZE + (70,), width=2)

    draw.text((140, 555), "④", font=f_num, fill=BRONZE, anchor="lm")
    draw.text((240, 555), "Brag Card", font=f_head, fill=IVORY, anchor="lm")

    brag_items = [
        "매달 1일 자동 생성 — 한 달 포트폴리오 한 장",
        "전체 수익률만 · 측정 기간 + 면책 병기",
        "종목명+수익률 동시 노출 없음 (의도된 설계)",
    ]
    y = 626
    for item in brag_items:
        draw.text((155, y), f"· {item}", font=f_body, fill=IVORY_D, anchor="lm")
        y += 46

    draw.text((W // 2, 875),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 24), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d14_slide3_features34.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D14-3 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D14 슬라이드 4 · "무엇을 하라고 말하지 않습니다"
# ═══════════════════════════════════════════════════════════════════════════════
def render_d14_slide4():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "4 / 5")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 62)
    f_sub  = _f(_KR_SANS, 32)

    draw.text((90, 130), "D14 · PRINCIPLE", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    draw.rectangle([80, 248, 88, 580], fill=BRONZE)

    draw.text((W // 2, 290), "무엇을 하라고",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 372), "말하지 않습니다.",
              font=f_head, fill=IVORY, anchor="mm")

    draw.text((W // 2, 508), "판단은 당신이.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 650),
              "내가 등록한 포트폴리오 기준으로",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 700),
              "자료를 정리해주는 정보 제공 도구.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    draw.text((W // 2, 810),
              "정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 26), fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 852),
              "과거 성과는 미래 수익을 보장하지 않습니다.",
              font=_f(_KR_SANS, 24), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d14_slide4_principle.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D14-4 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D14 슬라이드 5 · CTA — 베타 신청
# 결제 hook 없음 / 선착순·한정·마감임박·D-N 금지
# ═══════════════════════════════════════════════════════════════════════════════
def render_d14_slide5_cta():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "5 / 5")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 64)
    f_sub  = _f(_KR_SANS, 32)
    f_cta  = _f(_KR_SANS, 34)
    f_disc = _f(_KR_SANS, 24)

    draw.text((90, 130), "D14 · BETA", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 270), "정리된 브리핑 한 장,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 356), "직접 받아보세요.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 492),
              "지금 베타로 열어두고 있어요.",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 542),
              "완성형은 아니지만,",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 592),
              "매일 아침 브리핑이 어떤 느낌인지",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 642),
              "직접 받아보실 수 있어요.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # CTA 박스 (결제 hook 없음, 선착순/한정/마감임박/D-N 금지)
    draw.rectangle([160, 710, W - 160, 810], outline=BRONZE + (200,), width=2)
    draw.text((W // 2, 760),
              "프로필 링크에서 베타 신청",
              font=f_cta, fill=IVORY, anchor="mm")

    draw.text((W // 2, 865),
              "2주 동안 봐주셔서 정말 고맙습니다.",
              font=_f(_KR_SANS, 28), fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 905),
              "다음 주도 만든 거 그대로 올릴게요.",
              font=_f(_KR_SANS, 28), fill=IVORY_FAINT, anchor="mm")

    draw.rectangle([120, 930, W - 120, 932], fill=HAIRLINE)
    draw.text((W // 2, 958),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=f_disc, fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d14_slide5_cta.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D14-5 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"=== PivoxQuant D8~D14 Card Render ===")
    print(f"출력 디렉토리: {OUT_DIR}\n")

    # D8 — Brag Card (단일, 4:5, §101 4요소 병기)
    render_d8()

    # D9 — 모닝 브리핑 해부 (캐러셀 4장)
    render_d9_slide1()
    render_d9_slide2_placeholder()
    render_d9_slide3()
    render_d9_slide4()

    # D10 — "묻지 않아도 먼저 온다" (단일, 4:5)
    render_d10()

    # D11 — 실적 캘린더 (캐러셀 4장)
    render_d11_slide1()
    render_d11_slide2_placeholder()
    render_d11_slide3()
    render_d11_slide4()

    # D12 — 릴스 커버 (9:16)
    render_d12_reels_cover()

    # D13 — "데이터로 정리, 판단은 당신" (단일, 4:5)
    render_d13()

    # D14 — 기능 총정리 + CTA (캐러셀 5장)
    render_d14_slide1()
    render_d14_slide2()
    render_d14_slide3()
    render_d14_slide4()
    render_d14_slide5_cta()

    # 생성 결과 확인
    print("\n=== 생성 파일 목록 ===")
    total = 0
    for f in sorted(OUT_DIR.glob("*.png")):
        sz = f.stat().st_size
        total += sz
        print(f"  {f.name:50s}  {sz // 1024:>5} KB")
    print(f"\n총 {len(list(OUT_DIR.glob('*.png')))}개 파일  /  {total // 1024} KB")
