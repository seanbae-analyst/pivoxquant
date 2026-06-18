"""
PivoxQuant D1~D7 Instagram Card Renderer
-----------------------------------------
출력: docs/marketing/week1-cards/*.png
해상도: 1080×1080 (D1/D3/D5커버/D6) 또는 1080×1350 (4:5 세로형)

색상 토큰 (design v3 락-인):
  INK     = #050505  Vantablack
  BRONZE  = #B8956A
  IVORY   = #F5F0E8
  IVORY_D = rgba(245,240,232,0.65)  dim
  UP      = #D18888  carmine (KR 상승)
  DOWN    = #7AA0C8  indigo  (KR 하락)

§101 준수:
  - 권유어(사세요/매수/매도/추천/목표가) 0건
  - 수익률 수치 카드 없음
  - 더미 데이터 전용 (종목명 비식별)
"""

from __future__ import annotations
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── 경로 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "marketing" / "week1-cards"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 폰트 경로 (시스템 TTF) ────────────────────────────────────────────────────
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
# D1 · 단일 카드 1080×1080 — "당신은 CFO"
# ═══════════════════════════════════════════════════════════════════════════════
def render_d1():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)

    # 브론즈 수직 액센트 라인
    draw.rectangle([60, 100, 63, H - 100], fill=BRONZE + (40,))

    # 소제목 eyebrow
    f_eye = _f(_JETBRAINS_B, 22)
    draw.text((90, 130), "D1 · CONCEPT", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 메인 헤드라인 — 한글은 KR_SANS로
    f_head_kr = _f(_KR_SANS, 66)
    draw.text((W // 2, 300), "당신은 당신",
              font=f_head_kr, fill=IVORY, anchor="mm")
    draw.text((W // 2, 385), "포트폴리오의",
              font=f_head_kr, fill=IVORY, anchor="mm")

    # 강조 "CFO" — Playfair (영문) + 더 큰 사이즈
    f_cfo = _f(_PLAYFAIR, 150)
    draw.text((W // 2, 530), "CFO",
              font=f_cfo, fill=BRONZE, anchor="mm")

    # 입니다. — KR
    draw.text((W // 2, 625), "입니다.",
              font=f_head_kr, fill=IVORY, anchor="mm")

    # 서브 카피
    f_sub = _f(_KR_SANS, 34)
    draw.text((W // 2, 740),
              "판단은 당신이.  자료 정리는 저희가.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # 하단 브랜드
    draw_brand_mark(draw, W, H)

    out = OUT_DIR / "d1_cfo_card.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D1 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D2 슬라이드 1 · 훅 카드 1080×1080
# ═══════════════════════════════════════════════════════════════════════════════
def render_d2_slide1():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "1 / 3")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 72)   # 한글 헤드라인 → KR
    f_sub  = _f(_KR_SANS, 36)
    f_mono = _f(_JETBRAINS_B, 38)

    draw.text((90, 130), "D2 · MORNING BRIEF", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 310), "매일 아침 6시,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 400), "메일함에",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 490), "도착합니다.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 655), "모닝 브리핑",
              font=_f(_KR_SANS, 38), fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 710),
              "어젯밤 미국장 · 관련 뉴스 · 실적 일정",
              font=f_sub, fill=IVORY_MID, anchor="mm")
    draw.text((W // 2, 760),
              "한 장으로 정리",
              font=f_sub, fill=IVORY_MID, anchor="mm")

    # 스와이프 힌트
    f_hint = _f(_KR_SANS, 26)
    draw.text((W // 2, 870), "스와이프 →",
              font=f_hint, fill=BRONZE + (140,), anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d2_slide1_hook.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D2-1 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D2 슬라이드 2 자리표시 카드 (CEO 실제 캡처 대체용)
# ═══════════════════════════════════════════════════════════════════════════════
def render_d2_slide2_placeholder():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "2 / 3")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_note = _f(_KR_SANS, 36)
    f_sub  = _f(_KR_SANS, 28)
    f_tag  = _f(_JETBRAINS_B, 24)

    draw.text((90, 130), "D2 · MORNING BRIEF", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 점선 영역 (캡처 대체 구역)
    for y in range(200, 870, 18):
        draw.rectangle([120, y, W - 120, y + 1], fill=HAIRLINE)
    draw.rectangle([120, 200, W - 120, 870], outline=BRONZE + (60,), width=2)

    draw.text((W // 2, 500),
              "[ 실제 모닝 브리핑 화면 캡처 ]",
              font=f_note, fill=BRONZE + (140,), anchor="mm")
    draw.text((W // 2, 560),
              "CEO 캡처 삽입 위치",
              font=f_sub, fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 620),
              "개인정보 · 특정종목+수익률 노출 금지",
              font=f_sub, fill=IVORY_FAINT, anchor="mm")

    # AI 생성 라벨 (Bronze 좌상단)
    draw.rectangle([120, 200, 310, 248], fill=BRONZE + (200,))
    draw.text((215, 224), "AI 생성",
              font=_f(_KR_SANS, 24), fill=INK + (255,), anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d2_slide2_placeholder.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D2-2 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D2 슬라이드 3 · CTA
# ═══════════════════════════════════════════════════════════════════════════════
def render_d2_slide3():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "3 / 3")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 72)   # 한글 → KR
    f_sub  = _f(_KR_SANS, 32)
    f_cta  = _f(_KR_SANS, 34)
    f_tag  = _f(_JETBRAINS_B, 26)

    draw.text((90, 130), "D2 · MORNING BRIEF", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 310), "자는 동안",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 400), "정리해 둘게요.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 540),
              "차트 앱 다섯 개 켜고 손으로 모으던 걸,",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 585),
              "자는 동안 대신 정리해 둡니다.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # CTA 박스
    draw.rectangle([160, 660, W - 160, 760], outline=BRONZE + (200,), width=2)
    draw.text((W // 2, 710),
              "프로필 링크에서 샘플 보기",
              font=f_cta, fill=IVORY, anchor="mm")
    draw.text((W // 2, 750), "↓",
              font=f_tag, fill=BRONZE, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d2_slide3_cta.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D2-3 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D3 · 좌우 2분할 비교 카드 1080×1080
# ═══════════════════════════════════════════════════════════════════════════════
def render_d3():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 48)   # 한글 헤드라인 → KR
    f_pq   = _f(_JETBRAINS_B, 42)  # "PivoxQuant" 영문 → JetBrains
    f_sub  = _f(_KR_SANS, 30)
    f_body = _f(_KR_SANS, 27)

    draw.text((90, 130), "D3 · STRUCTURE", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 헤드라인 중앙
    draw.text((W // 2, 205), "구조의 차이",
              font=f_head, fill=IVORY, anchor="mm")

    MID = W // 2

    # ── 좌 패널 (대화형 AI) — 아주 어두운 charcoal ──
    LEFT_X = 270
    draw.rectangle([80, 260, MID - 15, 730],
                   fill=(20, 20, 20, 255))    # 거의 검정에 가까운 charcoal
    draw.rectangle([80, 260, MID - 15, 730],
                   outline=(245, 240, 232, 40), width=1)

    # 좌 패널 제목
    draw.text((LEFT_X, 303), "대화형 AI",
              font=f_head, fill=IVORY_MID, anchor="mm")
    draw.rectangle([100, 330, MID - 25, 332], fill=HAIRLINE)

    items_left = [
        "물어야 답한다",
        "종목 리스트 매번 입력",
        "그때그때 자유 질문",
    ]
    # 좌우 불릿 세로 시작 위치 통일: y=370
    y = 370
    for item in items_left:
        draw.text((LEFT_X, y), f"· {item}",
                  font=f_body, fill=IVORY_MID, anchor="mm")
        y += 54

    # ── 중앙 수직 점선 구분 ──
    for y_seg in range(260, 730, 16):
        draw.rectangle([MID - 1, y_seg, MID + 1, y_seg + 8],
                       fill=BRONZE + (100,))

    # ── 우 패널 (PivoxQuant) — Bronze wash ──
    RIGHT_X = MID + (W - MID - 80) // 2 + 10
    draw.rectangle([MID + 15, 260, W - 80, 730],
                   fill=(184, 149, 106, 22))
    draw.rectangle([MID + 15, 260, W - 80, 730],
                   outline=BRONZE + (60,), width=1)

    # 우 패널 제목 — 좌 패널과 동일 y 위치(303), bronze wash 위라 Ivory로 대비 확보
    draw.text((RIGHT_X, 303), "PivoxQuant",
              font=f_pq, fill=IVORY, anchor="mm")
    draw.rectangle([MID + 25, 330, W - 90, 332], fill=DIVIDER)

    items_right = [
        "자는 동안 정리된다",
        "포트폴리오 등록 1회",
        "정해진 시각에 자동 전달",
    ]
    # 좌우 불릿 세로 시작 위치 통일: y=370
    y = 370
    for item in items_right:
        draw.text((RIGHT_X, y), f"· {item}",
                  font=f_body, fill=IVORY, anchor="mm")
        y += 54

    # 하단 공통 메시지
    draw.text((W // 2, 810),
              "\"질문하면 답하는 방식\" vs \"묻기 전에 먼저 정리\"",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 858),
              "구조가 다른 것 · 어느 쪽이 낫다는 얘기 아님",
              font=_f(_KR_SANS, 24), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d3_comparison_card.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D3 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D4 슬라이드 1 · 훅
# ═══════════════════════════════════════════════════════════════════════════════
def render_d4_slide1():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "1 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 70)   # 한글 → KR
    f_sub  = _f(_KR_SANS, 34)

    draw.text((90, 130), "D4 · ARTIFACTS", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 310), "주말에도",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 395), "리포트는",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 480), "일합니다.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 630),
              "두 가지 정리 자료",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # 아이템 목록
    f_item = _f(_KR_SANS, 32)
    items = [
        ("위클리 메모",      "일요일 · 한 주 포트폴리오 변동 5p PDF"),
        ("실적 프리브리프",  "발표 전 · 과거 실적 추이 + 컨센서스"),
    ]
    y = 710
    for title, desc in items:
        draw.rectangle([120, y - 2, 126, y + 48], fill=BRONZE)
        draw.text((150, y + 24), title,
                  font=f_item, fill=IVORY, anchor="lm")
        draw.text((150, y + 60), desc,
                  font=_f(_KR_SANS, 26), fill=IVORY_D, anchor="lm")
        y += 110

    f_hint = _f(_KR_SANS, 26)
    draw.text((W // 2, 970), "스와이프 →",
              font=f_hint, fill=BRONZE + (140,), anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d4_slide1_hook.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D4-1 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D4 슬라이드 2 · 위클리 메모 목업 카드 (더미 데이터)
# ═══════════════════════════════════════════════════════════════════════════════
def render_d4_slide2_weekly():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "2 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 54)   # 한글 → KR
    f_sub  = _f(_KR_SANS, 28)
    f_mono = _f(_JETBRAINS, 26)
    f_tag  = _f(_JETBRAINS_B, 20)

    draw.text((90, 130), "D4 · WEEKLY MEMO", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # PDF 표지 목업 박스
    draw.rectangle([120, 190, W - 120, 730],
                   fill=(184, 149, 106, 10))
    draw.rectangle([120, 190, W - 120, 730],
                   outline=BRONZE + (80,), width=2)

    # PDF 헤더 라인
    draw.rectangle([120, 190, W - 120, 240], fill=BRONZE + (40,))
    draw.text((W // 2, 215), "WEEKLY MEMO",
              font=f_tag, fill=IVORY, anchor="mm")

    draw.text((W // 2, 320), "일요일, 5페이지 PDF",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 400),
              "한 주 포트폴리오 변동 정리",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # 더미 섹션 목록
    sections = [
        "포트폴리오 개요",
        "주간 시장 동향",
        "보유 종목 뉴스 요약",
        "다음 주 실적 일정",
        "관찰 포인트",
    ]
    f_sec = _f(_KR_SANS, 28)
    y = 475
    for i, sec in enumerate(sections, 1):
        draw.text((180, y), f"{i}.", font=f_mono, fill=BRONZE + (160,), anchor="lm")
        draw.text((220, y), sec, font=f_sec, fill=IVORY_MID, anchor="lm")
        y += 48

    # 더미 데이터 라벨
    draw.rectangle([120, 730, W - 120, 780],
                   fill=(5, 5, 5, 220))
    draw.text((W // 2, 755),
              "더미 데이터 · 실제 수치 미포함",
              font=_f(_KR_SANS, 20), fill=BRONZE + (160,), anchor="mm")

    draw.text((W // 2, 850),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 26), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d4_slide2_weekly_mock.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D4-2 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D4 슬라이드 3 · 실적 프리브리프 목업 (더미 데이터, 종목명 미표기)
# ═══════════════════════════════════════════════════════════════════════════════
def render_d4_slide3_earnings():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "3 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 54)   # 한글 → KR
    f_sub  = _f(_KR_SANS, 28)
    f_mono = _f(_JETBRAINS, 26)
    f_tag  = _f(_JETBRAINS_B, 20)

    draw.text((90, 130), "D4 · EARNINGS PRE-BRIEF", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    # 제목
    draw.text((W // 2, 280), "실적 발표 전,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 348), "데이터 먼저.",
              font=f_head, fill=BRONZE, anchor="mm")

    # 더미 실적 테이블 (종목명 미표기)
    draw.rectangle([120, 420, W - 120, 780],
                   fill=(184, 149, 106, 8))
    draw.rectangle([120, 420, W - 120, 780],
                   outline=BRONZE + (60,), width=1)

    # 테이블 헤더
    draw.rectangle([120, 420, W - 120, 464], fill=BRONZE + (30,))
    cols = ["종목", "발표 예정", "EPS 컨센서스", "전기 대비"]
    col_x = [180, 380, 620, 860]
    for cx, col in zip(col_x, cols):
        draw.text((cx, 442), col, font=_f(_KR_SANS, 20), fill=IVORY_MID, anchor="lm")

    # 더미 행 (비식별)
    rows_dummy = [
        ("종목 A", "D+3", "—", "—"),
        ("종목 B", "D+7", "—", "—"),
        ("종목 C", "D+10", "—", "—"),
    ]
    y = 490
    for row in rows_dummy:
        for cx, cell in zip(col_x, row):
            # 한글 포함 셀은 KR_SANS, 영문/숫자/em-dash는 f_mono
            has_kr = any('가' <= c <= '힣' for c in cell)
            cell_font = _f(_KR_SANS, 26) if has_kr else f_mono
            draw.text((cx, y), cell, font=cell_font,
                      fill=IVORY_MID, anchor="lm")
        y += 68
        draw.rectangle([140, y - 20, W - 140, y - 19], fill=HAIRLINE)

    draw.text((W // 2, 810),
              "종목명 미표기 · 더미 데이터",
              font=_f(_KR_SANS, 20), fill=BRONZE + (140,), anchor="mm")

    draw.text((W // 2, 876),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 26), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d4_slide3_earnings_mock.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D4-3 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D4 슬라이드 4 · CTA
# ═══════════════════════════════════════════════════════════════════════════════
def render_d4_slide4():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "4 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 66)   # 한글 → KR
    f_sub  = _f(_KR_SANS, 32)
    f_cta  = _f(_KR_SANS, 34)

    draw.text((90, 130), "D4 · ARTIFACTS", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 310), "판단은 당신이.",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 396), "정리는 저희가.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 540),
              "\"이거 해라\"가 아니라",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 590),
              "\"이 데이터들 보고 판단은 네가 해\"",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # CTA 박스
    draw.rectangle([160, 660, W - 160, 760], outline=BRONZE + (200,), width=2)
    draw.text((W // 2, 710),
              "프로필 링크에서 샘플 보기",
              font=f_cta, fill=IVORY, anchor="mm")

    draw.text((W // 2, 840),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 26), fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d4_slide4_cta.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D4-4 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D5 · 릴스 커버 1080×1920 (9:16)
# ═══════════════════════════════════════════════════════════════════════════════
def render_d5_reels_cover():
    """D5 릴스 커버 — 9:16. 커버답게 단순화: 훅+서브+포인트박스+AI라벨만.
    박스/텍스트 overflow 방지: y커서 누적 방식으로 배치."""
    W, H = 1080, 1920
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)

    f_eye  = _f(_JETBRAINS_B, 26)
    f_head = _f(_KR_SANS, 86)   # 한글 → KR
    f_sub  = _f(_KR_SANS, 42)
    f_body = _f(_KR_SANS, 36)
    f_tag  = _f(_JETBRAINS_B, 28)

    # ── eyebrow ──
    draw.text((90, 140), "D5 · REELS COVER", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # ── AI 생성 태그 (좌상단) ──
    draw.rectangle([80, 190, 330, 244], fill=BRONZE + (200,))
    draw.text((205, 217), "AI 생성 콘텐츠",
              font=_f(_KR_SANS, 26), fill=INK + (255,), anchor="mm")

    # ── 메인 훅 (y 커서 누적) ──
    y_cursor = 420
    head_lh = 110
    draw.text((W // 2, y_cursor), "내 주식",
              font=f_head, fill=IVORY, anchor="mm")
    y_cursor += head_lh
    draw.text((W // 2, y_cursor), "오늘 왜",
              font=f_head, fill=IVORY, anchor="mm")
    y_cursor += head_lh
    draw.text((W // 2, y_cursor), "올랐지?",
              font=f_head, fill=BRONZE, anchor="mm")
    y_cursor += 130   # 훅 → 서브 여백

    # ── 서브 카피 ──
    draw.text((W // 2, y_cursor),
              "검색하다 하루 다 갑니다.",
              font=f_sub, fill=IVORY_D, anchor="mm")
    y_cursor += 90

    # ── 포인트 박스 (y커서 기반, 텍스트 3줄 높이 계산 후 박스) ──
    BOX_PAD_TOP = 28
    BOX_LINE_H  = 66
    BOX_PAD_BOT = 28
    box_top = y_cursor + 20
    box_lines = [
        ("내가 가진 것들 기준으로",             IVORY_D),
        ("뉴스 흐름 · 데이터 관찰 포인트",       IVORY_D),
        ("정리된 자료부터 보고 판단은 내가.",     IVORY),   # bronze wash 위라 Ivory 사용
    ]
    box_h = BOX_PAD_TOP + BOX_LINE_H * len(box_lines) + BOX_PAD_BOT
    box_bot = box_top + box_h
    draw.rectangle([120, box_top, W - 120, box_bot],
                   fill=(184, 149, 106, 10))
    draw.rectangle([120, box_top, W - 120, box_bot],
                   outline=BRONZE + (60,), width=2)
    ty = box_top + BOX_PAD_TOP + BOX_LINE_H // 2
    for line_text, line_fill in box_lines:
        draw.text((W // 2, ty), line_text, font=f_body, fill=line_fill, anchor="mm")
        ty += BOX_LINE_H
    y_cursor = box_bot + 60

    # ── 자막 스펙 박스 (과밀 방지: 필수 정보만 5줄) ──
    cap_box_top = y_cursor
    captions = [
        ("0~3s",  '"내 주식 오늘 왜 올랐지?"'),
        ("3~12s", "뉴스 기반 관찰 포인트 정리 중"),
        ("12s~",  "정리됨. 판단은 내가."),
        ("끝",    "프로필 링크"),
    ]
    f_cap_t = _f(_JETBRAINS, 26)
    f_cap_c = _f(_KR_SANS, 27)
    CAP_LH  = 60
    cap_box_h = 52 + CAP_LH * len(captions) + 30
    cap_box_bot = cap_box_top + cap_box_h
    draw.rectangle([120, cap_box_top, W - 120, cap_box_bot],
                   fill=(18, 18, 18, 255))
    draw.rectangle([120, cap_box_top, W - 120, cap_box_bot],
                   outline=(184, 149, 106, 60), width=1)
    draw.text((W // 2, cap_box_top + 28), "자막 스펙",
              font=_f(_KR_SANS, 28), fill=BRONZE, anchor="mm")
    ty = cap_box_top + 62
    for ts, cap in captions:
        # 타임스탬프에 한글이 있으면 KR_SANS, 아니면 JetBrains
        ts_has_kr = any('가' <= c <= '힣' for c in ts)
        ts_font = _f(_KR_SANS, 26) if ts_has_kr else f_cap_t
        draw.text((155, ty), ts, font=ts_font, fill=BRONZE + (255,), anchor="lm")
        draw.text((325, ty), cap, font=f_cap_c, fill=IVORY + (255,), anchor="lm")
        ty += CAP_LH
    y_cursor = cap_box_bot + 50

    # ── 면책 ──
    draw.text((W // 2, min(y_cursor, H - 120)),
              "정보 제공 도구 · 투자자문 아님",
              font=_f(_KR_SANS, 28), fill=IVORY_FAINT, anchor="mm")
    draw_brand_mark(draw, W, H)

    out = OUT_DIR / "d5_reels_cover.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D5 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D6 · 세로 카드 1080×1350 (4:5) — 빌딩 인 퍼블릭
# ═══════════════════════════════════════════════════════════════════════════════
def render_d6():
    W, H = 1080, 1350
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)

    f_eye  = _f(_JETBRAINS_B, 22)
    f_tag  = _f(_JETBRAINS_B, 30)
    f_head = _f(_KR_SANS, 54)   # 한글 인용 → KR
    f_sub  = _f(_KR_SANS, 32)
    f_body = _f(_KR_SANS, 28)

    # Eyebrow (y=120, 텍스트 높이 ~22px → 하단 약 y=131)
    draw.text((90, 120), "D6 · BUILDING IN PUBLIC", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    # 상단 태그 — 영문은 JetBrains OK
    draw.text((W // 2, 210), "Building in Public",
              font=f_tag, fill=BRONZE, anchor="mm")

    # 중앙 인용 — 한글 → KR
    # 세로 Bronze 바: eyebrow 아래(y=155 이상) + 태그 위쪽과 충분한 간격 → y=280 시작
    draw.rectangle([80, 280, 86, 600], fill=BRONZE)  # 왼쪽 Bronze 바 — eyebrow 겹침 방지
    draw.text((W // 2, 315), "회사엔 CFO 보고서가",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 385), "올라온다.",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 475), "내 돈한텐 아무도",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 545), "안 올린다.",
              font=f_head, fill=IVORY, anchor="mm")

    # Bronze 강조 한 줄
    draw.text((W // 2, 672), "그래서 직접 만들었습니다.",
              font=_f(_KR_SANS, 44), fill=BRONZE, anchor="mm")

    # 서브 카피
    lines_body = [
        "챗봇 아닙니다.",
        "내가 등록한 포트폴리오 기준으로",
        "자료를 정리해서 메일로 보내주는 도구예요.",
        "판단은 사용자가, 정리는 저희가.",
    ]
    y = 790
    for line in lines_body:
        draw.text((W // 2, y), line, font=f_body, fill=IVORY_D, anchor="mm")
        y += 52

    # 1인 개발자
    draw.text((W // 2, 1075), "1인 개발자",
              font=f_sub, fill=BRONZE, anchor="mm")
    draw.text((W // 2, 1130),
              "디자인 · 코드 · 마케팅 혼자 합니다.",
              font=f_body, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 1180),
              "과정 그대로 여기 올릴게요.",
              font=f_body, fill=IVORY_D, anchor="mm")

    # 실사진 자리표시
    draw.rectangle([120, 120, 130, 1250], fill=HAIRLINE)

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d6_founder_story.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D6 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D7 슬라이드 1 · 회고 훅
# ═══════════════════════════════════════════════════════════════════════════════
def render_d7_slide1():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "1 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 70)   # 한글 → KR
    f_sub  = _f(_KR_SANS, 32)
    f_mono = _f(_JETBRAINS, 28)

    draw.text((90, 130), "D7 · WEEKLY RETROSPECTIVE", font=f_eye,
              fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 300), "출시 첫 주,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 385), "회고합니다.",
              font=f_head, fill=BRONZE, anchor="mm")

    # D1→D7 타임라인 점
    timeline = [
        ("D1", "컨셉 — 당신은 CFO"),
        ("D2", "모닝 브리핑"),
        ("D3", "구조의 차이"),
        ("D4", "위클리 메모 + 실적 프리브리프"),
        ("D5", "페인포인트 릴스"),
        ("D6", "빌딩 인 퍼블릭"),
        ("D7", "한 주 회고"),
    ]
    f_d = _f(_JETBRAINS_B, 26)
    f_t = _f(_KR_SANS, 26)
    y = 510
    for d_label, desc in timeline:
        # 점
        draw.ellipse([130, y - 8, 148, y + 8], fill=BRONZE)
        # 수직 연결선 (마지막 제외)
        if d_label != "D7":
            draw.rectangle([138, y + 8, 140, y + 46], fill=BRONZE + (80,))
        draw.text((165, y), d_label, font=f_d, fill=BRONZE, anchor="lm")
        draw.text((240, y), desc, font=f_t, fill=IVORY_D, anchor="lm")
        y += 54

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d7_slide1_hook.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D7-1 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D7 슬라이드 3 · 한 줄 요약
# ═══════════════════════════════════════════════════════════════════════════════
def render_d7_slide3():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "3 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 62)   # 한글 → KR
    f_sub  = _f(_KR_SANS, 32)
    f_disc = _f(_KR_SANS, 24)

    draw.text((90, 130), "D7 · SUMMARY", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    # 인용구 스타일 (왼쪽 Bronze 바)
    draw.rectangle([80, 260, 88, 640], fill=BRONZE)

    draw.text((W // 2, 308), "무엇을 하라고 정해주는 게 아니라,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 390), "정리된 자료.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 508), "판단은 당신이.",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 600),
              "내가 등록한 포트폴리오 기준으로",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 648),
              "자료를 정리해주는 정보 제공 도구",
              font=f_sub, fill=IVORY_D, anchor="mm")

    draw.text((W // 2, 780),
              "정보 제공 도구 · 투자자문 아님",
              font=f_disc, fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 820),
              "과거 성과는 미래 수익을 보장하지 않습니다",
              font=f_disc, fill=IVORY_FAINT, anchor="mm")
    draw.text((W // 2, 860),
              "투자 판단과 책임은 이용자 본인에게 있습니다",
              font=f_disc, fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d7_slide3_summary.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D7-3 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# D7 슬라이드 4 · 베타 CTA
# ═══════════════════════════════════════════════════════════════════════════════
def render_d7_slide4():
    W, H = 1080, 1080
    img, draw = make_canvas(W, H)
    draw_top_bar(draw, W)
    draw_bottom_bar(draw, W, H)
    draw_slide_num(draw, W, "4 / 4")

    f_eye  = _f(_JETBRAINS_B, 22)
    f_head = _f(_KR_SANS, 70)   # 한글 → KR
    f_sub  = _f(_KR_SANS, 32)
    f_cta  = _f(_KR_SANS, 34)
    f_tag  = _f(_JETBRAINS_B, 24)
    f_disc = _f(_KR_SANS, 24)

    draw.text((90, 130), "D7 · BETA CTA", font=f_eye, fill=BRONZE + (180,), anchor="lm")

    draw.text((W // 2, 290), "매일 아침,",
              font=f_head, fill=IVORY, anchor="mm")
    draw.text((W // 2, 380), "정리된 한 장.",
              font=f_head, fill=BRONZE, anchor="mm")

    draw.text((W // 2, 520),
              "지금 베타로 열어두고 있어요.",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 570),
              "완성형은 아니지만,",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 620),
              "매일 아침 브리핑 한 장이 어떤 느낌인지",
              font=f_sub, fill=IVORY_D, anchor="mm")
    draw.text((W // 2, 670),
              "직접 받아보실 수 있어요.",
              font=f_sub, fill=IVORY_D, anchor="mm")

    # CTA 박스 (결제 hook 없음, §101)
    draw.rectangle([160, 730, W - 160, 830], outline=BRONZE + (200,), width=2)
    draw.text((W // 2, 780),
              "프로필 링크에서 베타 신청",
              font=f_cta, fill=IVORY, anchor="mm")

    draw.text((W // 2, 880),
              "피드백 하나하나가 다음 주 업데이트로",
              font=_f(_KR_SANS, 28), fill=IVORY_FAINT, anchor="mm")

    draw.rectangle([120, 912, W - 120, 914], fill=HAIRLINE)
    draw.text((W // 2, 940),
              "AI 생성 · 정보 제공 도구 · 투자자문 아님",
              font=f_disc, fill=IVORY_FAINT, anchor="mm")

    draw_brand_mark(draw, W, H)
    out = OUT_DIR / "d7_slide4_beta_cta.png"
    img.convert("RGB").save(out, "PNG", optimize=True)
    print(f"D7-4 saved: {out}  ({out.stat().st_size // 1024} KB)")


# ═══════════════════════════════════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=== PivoxQuant D1~D7 Card Render ===")
    print(f"출력 디렉토리: {OUT_DIR}\n")

    render_d1()
    render_d2_slide1()
    render_d2_slide2_placeholder()
    render_d2_slide3()
    render_d3()
    render_d4_slide1()
    render_d4_slide2_weekly()
    render_d4_slide3_earnings()
    render_d4_slide4()
    render_d5_reels_cover()
    render_d6()
    render_d7_slide1()
    render_d7_slide3()
    render_d7_slide4()

    # 생성 결과 확인
    print("\n=== 생성 파일 목록 ===")
    total = 0
    for f in sorted(OUT_DIR.glob("*.png")):
        sz = f.stat().st_size
        total += sz
        print(f"  {f.name:45s}  {sz // 1024:>5} KB")
    print(f"\n총 {len(list(OUT_DIR.glob('*.png')))}개 파일  /  {total // 1024} KB")
