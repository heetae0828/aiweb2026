"""
AI 국내 여행 도우미 (단일 페이지)
MBTI 여행지 추천 + 1일차/2일차별 일정표 + PDF 다운로드
"""
import json
import os
import re
import tempfile
import urllib.parse

import gradio as gr
import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from openai import OpenAI

matplotlib.use("Agg")
load_dotenv()

MAX_MEMBERS = 15

# ── 상수 ────────────────────────────────────────────────────────────────────
MBTI_LIST = [
    "ISTJ", "ISFJ", "INTJ", "INFJ",
    "ISTP", "ISFP", "INTP", "INFP",
    "ESTJ", "ESFJ", "ENTJ", "ENFJ",
    "ESTP", "ESFP", "ENTP", "ENFP",
]
REGION_TREE = {
    "(필수 선택)": [],
    "서울/경기/인천": ["서울", "인천", "수원", "성남", "고양", "부천", "안산", "안양", "용인", "광명", "평택", "시흥", "파주", "의정부", "김포", "하남", "광주", "양주", "구리", "남양주", "화성", "이천", "여주", "가평", "양평"],
    "강원": ["춘천", "강릉", "원주", "속초", "동해", "태백", "삼척", "홍천", "횡성", "평창", "정선", "철원", "화천", "양구", "인제", "고성", "양양"],
    "충청": ["대전", "청주", "충주", "천안", "아산", "공주", "보령", "서산", "논산", "계룡", "당진", "제천", "단양", "음성", "진천", "괴산", "증평", "세종"],
    "전라": ["광주", "전주", "익산", "군산", "정읍", "남원", "김제", "목포", "여수", "순천", "나주", "광양", "담양", "곡성", "구례", "고흥", "보성", "화순", "장흥", "강진", "해남", "영암", "무안", "함평", "영광", "장성", "완도", "진도", "신안"],
    "경상": ["부산", "대구", "울산", "경주", "포항", "안동", "구미", "영주", "영천", "상주", "문경", "경산", "창원", "진주", "통영", "사천", "김해", "밀양", "거제", "양산", "의령", "함안", "창녕", "고성", "남해", "하동", "산청", "함양", "거창", "합천"],
    "제주": ["제주"],
}
REGION_PROVINCES = list(REGION_TREE.keys())
THEMES = ["자연/힐링", "맛집 탐방", "역사/문화", "액티비티/스포츠", "도시/쇼핑", "야경/감성", "온천/스파"]
MBTI_TRAITS = {
    "ISTJ": "계획적이고 꼼꼼함. 역사 유적지, 박물관, 전통문화 체험 선호. 검증된 맛집과 안정적인 일정 중시",
    "ISFJ": "배려심 깊고 조용함. 자연 속 힐링, 온천, 소박한 마을 투어 선호. 편안하고 아늑한 숙소 중시",
    "INFJ": "통찰력 있고 감성적. 철학적 분위기의 사찰, 고즈넉한 문화유산, 조용한 자연 선호",
    "INTJ": "전략적 계획형. 효율적인 동선, 건축·역사 탐방, 심층 투어 선호. 혼잡한 관광지 기피",
    "ISTP": "자유롭고 모험적. 낚시, 트레킹, 드라이브 코스 등 손으로 직접 하는 액티비티 선호",
    "ISFP": "예술적 감각. 감성 카페, 공방 체험, 아름다운 자연경관, 로컬 시장 선호",
    "INFP": "낭만적이고 감성적. 문학 기행, 독립 서점, 조용한 해변·숲, 감성 숙소 선호",
    "INTP": "지적 호기심 강함. 과학관, 특이한 건축물, 잘 알려지지 않은 숨은 명소 탐방 선호",
    "ESTP": "활동적이고 즉흥적. 서핑, 번지점프, 스키, 핫플레이스 등 스릴 있는 액티비티 선호",
    "ESFP": "흥이 많고 사교적. 축제, 공연, 야시장, 화려한 야경, 인생샷 명소 선호",
    "ENFP": "열정적이고 창의적. 독특한 테마 마을, 이색 체험, 새로운 음식 탐험 선호",
    "ENTP": "도전적이고 논쟁적. 색다른 코스, 논쟁거리 있는 역사 현장, 실험적인 레스토랑 선호",
    "ESTJ": "실용적 리더형. 효율 중심의 유명 관광지, 대형 리조트, 잘 정리된 패키지형 일정 선호",
    "ESFJ": "사교적이고 배려적. 맛집 투어, 쇼핑, 가족·단체 여행지, 분위기 좋은 카페 선호",
    "ENFJ": "따뜻한 리더십. 지역 문화 교류, 봉사 투어, 사람 냄새 나는 전통시장·마을 선호",
    "ENTJ": "목표지향적. 럭셔리 리조트, 골프·요트 등 고급 액티비티, 비즈니스형 여행 선호",
}
DURATIONS = ["당일치기", "1박2일", "2박3일", "3박4일", "4박5일 이상"]
DURATION_DAYS = {"당일치기": 1, "1박2일": 2, "2박3일": 3, "3박4일": 4, "4박5일 이상": 5}

# ── 한국어 폰트 ──────────────────────────────────────────────────────────────
def _find_ko_font():
    for f in fm.findSystemFonts():
        if "nanumgothic" in os.path.basename(f).lower():
            return f
    for f in fm.findSystemFonts():
        b = os.path.basename(f).lower()
        if "applesd" in b or ("nanum" in b and "gothic" in b):
            return f
    return None

_KO_FONT_PATH = _find_ko_font()
if _KO_FONT_PATH:
    fm.fontManager.addfont(_KO_FONT_PATH)
    _KO_FONT = fm.FontProperties(fname=_KO_FONT_PATH)
    plt.rcParams["font.family"] = _KO_FONT.get_name()
else:
    _KO_FONT = None
plt.rcParams["axes.unicode_minus"] = False


# ── UI 헬퍼 ─────────────────────────────────────────────────────────────────
def compute_count(val):
    return int(val) if val else 1


def update_rows_count(val):
    n = int(val) if val else 1
    return [gr.update(visible=(i < n)) for i in range(MAX_MEMBERS)]


def update_city_dropdown(province: str):
    cities = REGION_TREE.get(province, [])
    if not cities:
        return gr.update(choices=["(선택 사항)"], value="(선택 사항)")
    return gr.update(choices=["(선택 사항)"] + cities, value="(선택 사항)")


def toggle_custom_days(duration: str):
    return gr.update(visible=(duration == "4박5일 이상"))


def limit_themes(themes):
    if len(themes) > 2:
        return gr.update(value=themes[:2])
    return gr.update(value=themes)


# ── 통합 프롬프트 ────────────────────────────────────────────────────────────
def _build_prompt(members, duration_label, n_days, region, themes):
    member_lines = "\n".join(
        f"  - 멤버{i+1}: MBTI={m[0] or '미입력'} ({MBTI_TRAITS.get(m[0], '정보 없음') if m[0] else ''}), 성별={m[1]}, 나이={int(m[2])}세"
        for i, m in enumerate(members)
    )
    region_line = f"선호 지역: {region}" if region and region not in ("(필수 선택)", "(선택 사항)") else "지역 무관"
    themes_line = f"선호 테마: {', '.join(themes)}" if themes else "테마 무관"
    schedule_keys = ", ".join(f'"{i+1}일차": [...]' for i in range(n_days))
    is_food = "맛집 탐방" in themes
    has_stay = n_days > 1

    food_schema = ""
    if is_food:
        food_schema = """,
  "restaurants": {
    "아침": [{"name": "식당명", "address": "주소", "desc": "한 줄 설명", "price": "1인 가격대"}, ...10개],
    "점심": [...10개],
    "저녁": [...10개],
    "카페": [...10개],
    "분위기맛집": [...10개]
  }"""

    food_rule = ""
    if is_food:
        food_rule = """
- restaurants: 아침/점심/저녁/카페/분위기맛집 각 10개, 전체 50개 중복 없이. 반드시 실제로 영업 중인 검증된 가게만 추천하라. 가게 이름, 실제 도로명 주소, 한 줄 설명, 1인 가격대 포함. 불확실하거나 폐업했을 가능성이 있는 곳은 절대 포함하지 마라."""

    stay_rule = ""
    if has_stay:
        stay_rule = """
- accommodation: 추천 숙소 3곳의 name(숙소명), area(위치 동네), type(펜션/호텔/게스트하우스 등), price_per_night(1박 가격대) 포함."""
        stay_schema = """,
  "accommodation": [
    {"name": "숙소명", "area": "위치", "type": "숙소유형", "price_per_night": "가격대"},
    {"name": "숙소명", "area": "위치", "type": "숙소유형", "price_per_night": "가격대"},
    {"name": "숙소명", "area": "위치", "type": "숙소유형", "price_per_night": "가격대"}
  ]"""
    else:
        stay_schema = ""

    return f"""당신은 국내 여행 전문가이자 MBTI 전문가입니다.
아래 정보를 바탕으로 여행지 추천과 상세 일정을 하나의 JSON으로 작성해주세요.

[여행 멤버]
{member_lines}

[여행 조건]
- 여행 기간: {duration_label} (총 {n_days}일)
- {region_line}
- {themes_line}

반드시 순수 JSON만 출력하세요 (마크다운 코드블록 없이):
{{
  "top_destination": "1위 여행지명",
  "trip_concept": "이번 여행의 컨셉 한 줄 (예: 부산 핫플 찍먹 투어, 제주 동쪽 완전 정복 등)",
  "recommendations": [
    {{"rank": 1, "name": "여행지명", "address": "도로명주소 (시/군/구/동 포함)", "reason": "MBTI와 연결한 선정 이유 2~3문장"}},
    {{"rank": 2, "name": "여행지명", "address": "도로명주소", "reason": "선정 이유 2~3문장"}},
    {{"rank": 3, "name": "여행지명", "address": "도로명주소", "reason": "선정 이유 2~3문장"}}
  ],
  "mbti_analysis": "MBTI 조합 여행 스타일을 재미있게 3~4문장",
  "tips": ["팁1", "팁2", "팁3"],
  "schedule": {{{schedule_keys}}}{food_schema}{stay_schema}
}}

일정 항목 형식:
{{"시간": "HH:MM", "장소": "장소명", "활동": "활동명", "상세내용": "설명 1~2문장", "이동수단": "교통수단"}}

일정 작성 규칙:
- 오전부터 마지막 날 저녁까지 빠짐없이 작성. 식사/이동/관광/숙박 모두 포함.
- 【동선 핵심】지리적으로 한 방향으로 흘러가는 일정을 짜라. A→B→C→D처럼 이동하되 같은 곳을 왕복하지 마라.
- 하루에 여러 도시를 억지로 넣지 말고, 한 지역을 깊게 파거나 인접 지역을 자연스럽게 연결하라.
- 예를 들어 서울/경기/인천이면: "홍대-연남동-마포 감성 투어" 처럼 하나의 컨셉으로 동선을 묶어라.{food_rule}{stay_rule}
"""


# ── HTML 일정표 생성 ─────────────────────────────────────────────────────────
def _schedule_html(schedule: dict) -> str:
    if not schedule:
        return ""

    parts = ['<div style="font-family:\'Apple SD Gothic Neo\',\'Nanum Gothic\',sans-serif">']

    for day, events in schedule.items():
        parts.append(f"""
  <div style="margin-bottom:20px">
    <div style="background:#1D4ED8;color:white;padding:7px 14px;
                border-radius:8px 8px 0 0;font-weight:bold;font-size:14px">
      📅 {day}
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:12.5px">
      <tr style="background:#DBEAFE;text-align:center">
        <th style="padding:6px;border:1px solid #93C5FD;width:8%">시간</th>
        <th style="padding:6px;border:1px solid #93C5FD;width:16%">장소</th>
        <th style="padding:6px;border:1px solid #93C5FD;width:15%">활동</th>
        <th style="padding:6px;border:1px solid #93C5FD;width:46%">상세 내용</th>
        <th style="padding:6px;border:1px solid #93C5FD;width:15%">이동수단</th>
      </tr>""")
        for i, e in enumerate(events):
            bg = "#F0F7FF" if i % 2 == 0 else "#FFFFFF"
            parts.append(f"""
      <tr style="background:{bg}">
        <td style="padding:6px;border:1px solid #BFDBFE;font-weight:bold;
                   color:#1E40AF;text-align:center">{e.get('시간','')}</td>
        <td style="padding:6px;border:1px solid #BFDBFE;text-align:center">{e.get('장소','')}</td>
        <td style="padding:6px;border:1px solid #BFDBFE;text-align:center">{e.get('활동','')}</td>
        <td style="padding:6px;border:1px solid #BFDBFE">{e.get('상세내용','')}</td>
        <td style="padding:6px;border:1px solid #BFDBFE;text-align:center;
                   color:#6B7280;font-size:12px">{e.get('이동수단','')}</td>
      </tr>""")
        parts.append("\n    </table>\n  </div>")

    parts.append("\n</div>")
    return "".join(parts)


# ── PDF 생성 ─────────────────────────────────────────────────────────────────
def _make_pdf(data: dict) -> str | None:
    schedule = data.get("schedule", {})
    top_dest = data.get("top_destination", "여행지")
    fp_kw    = {"fontproperties": _KO_FONT} if _KO_FONT else {}

    rows, row_colors = [], []
    COLS = ["시간", "장소", "활동", "상세내용", "이동수단"]

    for day, events in schedule.items():
        rows.append([day, "", "", "", ""])
        row_colors.append(["#DBEAFE"] * 5)
        for idx, e in enumerate(events):
            rows.append([e.get(c, "") for c in COLS])
            row_colors.append(["#F0F7FF" if idx % 2 == 0 else "#FFFFFF"] * 5)

    if not rows:
        return None

    fig_h = max(12, len(rows) * 0.38 + 4)
    fig, ax = plt.subplots(figsize=(17, fig_h))
    ax.axis("off")

    fig.text(0.5, 0.995, f"{top_dest} 여행 일정표",
             ha="center", va="top", fontsize=18, fontweight="bold", **fp_kw)

    col_w = [0.07, 0.13, 0.14, 0.50, 0.16]
    all_cells = [COLS] + rows
    all_colors = [["#1D4ED8"] * 5] + row_colors

    table = ax.table(cellText=all_cells, colWidths=col_w,
                     loc="center", bbox=[0, 0, 1, 0.94])
    table.auto_set_font_size(False)
    table.set_fontsize(9)

    for j in range(5):
        c = table[0, j]
        c.set_facecolor("#1D4ED8")
        c.set_text_props(color="white", fontweight="bold", **fp_kw)
        c.set_edgecolor("#1E40AF")

    for i in range(1, len(all_cells)):
        is_day_row = (all_cells[i][1] == "" and len(all_cells[i][0]) <= 4)
        for j in range(5):
            c = table[i, j]
            c.set_facecolor(all_colors[i][j])
            c.set_edgecolor("#BFDBFE")
            if is_day_row and j == 0:
                c.set_text_props(fontweight="bold", color="#1E40AF", **fp_kw)
            else:
                c.set_text_props(**fp_kw)

    tmp = tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False, prefix=f"travel_{top_dest}_")
    fig.savefig(tmp.name, format="pdf", bbox_inches="tight")
    plt.close(fig)
    return tmp.name


# ── 메인 함수 ────────────────────────────────────────────────────────────────
def run_all(
    count,
    mbti1, gender1, age1,
    mbti2, gender2, age2,
    mbti3, gender3, age3,
    mbti4, gender4, age4,
    mbti5, gender5, age5,
    mbti6, gender6, age6,
    mbti7, gender7, age7,
    mbti8, gender8, age8,
    mbti9, gender9, age9,
    mbti10, gender10, age10,
    mbti11, gender11, age11,
    mbti12, gender12, age12,
    mbti13, gender13, age13,
    mbti14, gender14, age14,
    mbti15, gender15, age15,
    duration, custom_days_val, province, city, themes,
):
    actual_count = compute_count(count)
    all_data = [
        (mbti1, gender1, age1), (mbti2, gender2, age2),
        (mbti3, gender3, age3), (mbti4, gender4, age4),
        (mbti5, gender5, age5), (mbti6, gender6, age6),
        (mbti7, gender7, age7), (mbti8, gender8, age8),
        (mbti9, gender9, age9), (mbti10, gender10, age10),
        (mbti11, gender11, age11), (mbti12, gender12, age12),
        (mbti13, gender13, age13), (mbti14, gender14, age14),
        (mbti15, gender15, age15),
    ]
    # 3인 미만이면 MBTI 필수, 3인 이상이면 선택
    mbti_required = actual_count < 3

    active = []
    for i in range(actual_count):
        mbti, gender, age = all_data[i]
        if not mbti and mbti_required:
            yield f"❌ 멤버{i+1}의 MBTI를 선택해주세요.", "", "", gr.update(visible=False, value=None)
            return
        if not age or age <= 0:
            yield f"❌ 멤버{i+1}의 나이를 입력해주세요.", "", "", gr.update(visible=False, value=None)
            return
        active.append((mbti or None, gender, age))

    # 여행 기간 결정
    if duration == "4박5일 이상" and custom_days_val and custom_days_val >= 5:
        n_days = int(custom_days_val)
        duration_label = f"{n_days-1}박{n_days}일"
    else:
        n_days = DURATION_DAYS.get(duration, 1)
        duration_label = duration

    # 선택된 지역 결정
    region = ""
    if city and city not in ("(선택 사항)", None):
        region = city
    elif province and province not in ("(필수 선택)", None):
        region = province

    if not region and not themes:
        yield "❌ 지역 또는 테마 중 하나 이상 선택해주세요.", "", "", gr.update(visible=False, value=None)
        return

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        yield "❌ OPENAI_API_KEY가 설정되지 않았습니다.", "", "", gr.update(visible=False, value=None)
        return

    def _loading_html(msg, step, total=6):
        bar = "█" * step + "░" * (total - step)
        return f"""<div style="font-family:'Apple SD Gothic Neo','Nanum Gothic',sans-serif;
                              padding:32px 24px;text-align:center">
  <div style="font-size:42px;margin-bottom:16px">✈️</div>
  <div style="font-size:18px;font-weight:bold;color:#1D4ED8;margin-bottom:10px">{msg}</div>
  <div style="font-size:22px;letter-spacing:4px;color:#3B82F6;margin-bottom:8px">{bar}</div>
  <div style="font-size:13px;color:#6B7280">AI가 최적의 여행 계획을 만들고 있습니다 — 잠시만 기다려주세요 🙏</div>
</div>"""

    try:
        client = OpenAI(api_key=api_key)
        prompt = _build_prompt(active, duration_label, n_days, region, themes)

        # ── 스트리밍 로딩 메시지 ──────────────────────────────────────────
        step_msgs = [
            ("🔍 멤버 MBTI 성향을 분석하는 중...", 1),
            ("🗺️ 최적의 여행지를 탐색하는 중...", 2),
            ("📅 맞춤 여행 일정을 구성하는 중...", 3),
            ("🍽️ 맛집 & 숙소 정보를 수집하는 중...", 4),
            ("📝 여행 계획서를 다듬는 중...", 5),
        ]
        step_thresholds = [100, 500, 1200, 2200, 3500]
        step_idx = 0

        yield _loading_html("🚀 여행 플랜 생성을 시작합니다!", 0), "", "", gr.update(visible=False, value=None)

        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "당신은 10년 경력의 국내 여행 전문가이자 MBTI 심리 전문가입니다. "
                    "여행자의 성향을 깊이 이해하고, 실제로 가볼 만한 숨은 명소와 검증된 맛집을 포함해 "
                    "현실적이고 알찬 일정을 구성합니다. "
                    "맛집 추천 시 실제 영업 중인 가게만 추천하고, 주소도 실제 도로명 주소를 정확히 기재하세요. "
                    "불확실하거나 폐업 가능성이 있는 곳은 절대 추천하지 마세요. "
                    "답변은 항상 따뜻하고 친근한 말투로, 여행이 기대되도록 생생하게 작성합니다. "
                    "반드시 요청한 JSON 형식만 출력하세요."
                )},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8192,
            stream=True,
        )

        raw = ""
        token_count = 0
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            raw += token
            token_count += len(token)
            while step_idx < len(step_thresholds) and token_count >= step_thresholds[step_idx]:
                msg, step = step_msgs[step_idx]
                yield _loading_html(msg, step), "", "", gr.update(visible=False, value=None)
                step_idx += 1

        raw = raw.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group() if m else raw)

        top_dest  = data.get("top_destination", "여행지")
        recs      = data.get("recommendations", [])
        mbti_a    = data.get("mbti_analysis", "")
        tips      = data.get("tips", [])
        concept   = data.get("trip_concept", "")
        medals    = ["🥇", "🥈", "🥉"]
        is_food   = "맛집 탐방" in themes
        has_stay  = n_days > 1

        rec_html = '<div style="font-family:\'Apple SD Gothic Neo\',\'Nanum Gothic\',sans-serif">'

        # 여행 컨셉
        if concept:
            rec_html += f'<div style="background:#EFF6FF;border:2px solid #3B82F6;border-radius:10px;padding:10px 16px;margin-bottom:16px;font-size:15px;font-weight:bold;color:#1D4ED8">🎯 {concept}</div>'

        rec_html += '<h2 style="color:#1D4ED8">🏆 추천 여행지 TOP 3</h2>'
        for i, r in enumerate(recs):
            addr = r.get("address", "")
            naver_url = f"https://map.naver.com/p/search/{urllib.parse.quote(addr)}" if addr else ""
            addr_html = (
                f'<a href="{naver_url}" target="_blank" '
                f'style="color:#2563EB;font-size:13px;text-decoration:none">'
                f'📍 {addr}</a>'
            ) if addr else ""
            rec_html += f"""
<div style="background:#F0F7FF;border-left:4px solid #3B82F6;
            padding:12px 16px;margin-bottom:14px;border-radius:0 8px 8px 0">
  <div style="font-size:16px;font-weight:bold;margin-bottom:4px">
    {medals[i] if i < 3 else str(i+1)+'.'} {r.get('name','')}
  </div>
  <div style="margin-bottom:6px">{addr_html}</div>
  <div style="font-size:13.5px;color:#374151;line-height:1.6">{r.get('reason','')}</div>
</div>"""

        rec_html += f"""
<hr style="border:none;border-top:1px solid #E5E7EB;margin:16px 0">
<h2 style="color:#1D4ED8">🧠 멤버 조합 분석</h2>
<p style="font-size:13.5px;line-height:1.7;color:#374151">{mbti_a}</p>
<hr style="border:none;border-top:1px solid #E5E7EB;margin:16px 0">
<h2 style="color:#1D4ED8">💡 여행 꿀팁</h2>
<ol style="font-size:13.5px;line-height:1.9;color:#374151">"""
        for tip in tips:
            rec_html += f"<li>{tip}</li>"
        rec_html += "</ol>"

        # ── 숙박 추천 + 예약 링크 ──────────────────────────────────────────
        if has_stay:
            top_dest_q = urllib.parse.quote(top_dest)
            yeogi_url  = f"https://www.yeogi.com/search?keyword={top_dest_q}&numberOfPeople={actual_count}"
            agoda_url  = f"https://www.agoda.com/ko-kr/search?city={top_dest_q}&rooms=1&adults={actual_count}"
            rec_html += f"""
<hr style="border:none;border-top:1px solid #E5E7EB;margin:16px 0">
<h2 style="color:#1D4ED8">🏨 숙소 예약</h2>
<p style="font-size:13px;color:#6B7280;margin-bottom:10px">
  {actual_count}명 기준으로 검색합니다. 아래 버튼을 클릭하면 바로 연결됩니다.
</p>
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px">
  <a href="{yeogi_url}" target="_blank"
     style="background:#FF5A5F;color:white;padding:10px 18px;border-radius:8px;
            text-decoration:none;font-weight:bold;font-size:14px">
    🏠 여기어때에서 찾기
  </a>
  <a href="{agoda_url}" target="_blank"
     style="background:#5C2D8C;color:white;padding:10px 18px;border-radius:8px;
            text-decoration:none;font-weight:bold;font-size:14px">
    🌐 아고다에서 찾기
  </a>
</div>"""
            # AI 추천 숙소 목록
            accommodations = data.get("accommodation", [])
            if accommodations:
                rec_html += '<div style="display:flex;flex-direction:column;gap:8px">'
                for acc in accommodations:
                    acc_q = urllib.parse.quote(f"{acc.get('name','')} {acc.get('area','')}")
                    yeogi_acc = f"https://www.yeogi.com/search?keyword={acc_q}&numberOfPeople={actual_count}"
                    rec_html += f"""
<div style="background:#FFF5F5;border-left:4px solid #FF5A5F;padding:10px 14px;border-radius:0 8px 8px 0">
  <div style="font-weight:bold;font-size:14px;margin-bottom:2px">
    🏨 {acc.get('name','')} <span style="color:#6B7280;font-weight:normal;font-size:12px">({acc.get('area','')} · {acc.get('type','')})</span>
  </div>
  <div style="font-size:13px;color:#374151;margin-bottom:6px">1박 {acc.get('price_per_night','')}</div>
  <a href="{yeogi_acc}" target="_blank"
     style="font-size:12px;color:#FF5A5F;text-decoration:none">여기어때에서 검색 →</a>
</div>"""
                rec_html += '</div>'

        # ── 맛집 리스트 ────────────────────────────────────────────────────
        if is_food:
            restaurants = data.get("restaurants", {})
            cat_icons = {"아침": "🌅", "점심": "☀️", "저녁": "🌙", "카페": "☕", "분위기맛집": "✨"}
            if restaurants:
                rec_html += """
<hr style="border:none;border-top:1px solid #E5E7EB;margin:16px 0">
<h2 style="color:#1D4ED8">🍽️ 맛집 리스트</h2>"""
                for cat, icon in cat_icons.items():
                    items = restaurants.get(cat, [])
                    if not items:
                        continue
                    cat_id = cat.replace(" ", "_")
                    rec_html += f'<h3 style="color:#1E40AF;margin:14px 0 8px">{icon} {cat}</h3>'

                    def _item_card(item):
                        name    = item.get("name", "")
                        addr    = item.get("address", "")
                        desc    = item.get("desc", "")
                        price   = item.get("price", "")
                        map_url = f"https://map.naver.com/p/search/{urllib.parse.quote(name+' '+addr)}" if name else ""
                        return f"""<div style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:8px;padding:10px 12px">
  <div style="font-weight:bold;font-size:13.5px;margin-bottom:2px">
    <a href="{map_url}" target="_blank" style="color:#92400E;text-decoration:none">{name} 📍</a>
  </div>
  <div style="font-size:12px;color:#6B7280;margin-bottom:4px">{addr}</div>
  <div style="font-size:12.5px;color:#374151;margin-bottom:4px">{desc}</div>
  <div style="font-size:12px;font-weight:bold;color:#B45309">{price}</div>
</div>"""

                    shown = items[:3]
                    hidden = items[3:]
                    rec_html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px">'
                    for item in shown:
                        rec_html += _item_card(item)
                    rec_html += '</div>'

                    if hidden:
                        rec_html += f'<div id="more_{cat_id}" style="display:none;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px;margin-top:8px">'
                        for item in hidden:
                            rec_html += _item_card(item)
                        rec_html += '</div>'
                        rec_html += f"""<button onclick="(function(){{
  var m=document.getElementById('more_{cat_id}');
  var b=document.getElementById('btn_{cat_id}');
  if(m.style.display==='none'){{m.style.display='grid';b.textContent='▲ 접기';}}
  else{{m.style.display='none';b.textContent='+ 더보기 ({len(hidden)}개)';}}
}})()" id="btn_{cat_id}"
  style="margin-top:8px;padding:7px 16px;background:#FFFBEB;border:1px solid #FCD34D;
         border-radius:6px;cursor:pointer;font-size:13px;color:#92400E;font-weight:bold">
  + 더보기 ({len(hidden)}개)
</button>"""

        rec_html += "</div>"

        schedule   = data.get("schedule", {})
        sched_html = _schedule_html(schedule)

        pdf_path = _make_pdf(data)

        if pdf_path:
            pdf_link_html = f'''<div class="pdf-download-link" style="margin-top:16px">
  <a href="/file={pdf_path}" download="{top_dest}_여행일정표.pdf">
    📥 {top_dest}_여행일정표.pdf — 클릭하여 다운로드
  </a>
</div>'''
        else:
            pdf_link_html = ""

        yield rec_html, sched_html, pdf_link_html, gr.update(visible=bool(pdf_path), value=pdf_path)

    except json.JSONDecodeError as e:
        yield f"<p>❌ 응답 파싱 오류: {e}</p>", "", "", gr.update(visible=False, value=None)
    except Exception as e:
        yield f"<p>❌ 오류: {e}</p>", "", "", gr.update(visible=False, value=None)


# ══════════════════════════════════════════════════════════════════════════════
# Gradio UI  (단일 페이지)
# ══════════════════════════════════════════════════════════════════════════════
CSS = """
/* MBTI 드롭다운 열렸을 때 페이지 스크롤 방지 */
.gradio-dropdown .dropdown-arrow { pointer-events: none; }
ul[role="listbox"] {
    max-height: 240px !important;
    overflow-y: auto !important;
    overscroll-behavior: contain !important;
}
/* 다크모드 강제 라이트 오버라이드 */
:root, [data-theme="dark"], .dark {
    --body-background-fill: #F8FAFF !important;
    --background-fill-primary: #FFFFFF !important;
    --background-fill-secondary: #EFF6FF !important;
    --border-color-primary: #BFDBFE !important;
    --color-accent: #2563EB !important;
    --color-accent-soft: #DBEAFE !important;
    --button-primary-background-fill: #2563EB !important;
    --button-primary-text-color: #FFFFFF !important;
    --block-title-text-color: #1E3A8A !important;
    --body-text-color: #1E293B !important;
    --block-label-text-color: #1E3A8A !important;
    --input-background-fill: #FFFFFF !important;
    --input-border-color: #93C5FD !important;
    --checkbox-background-color: #FFFFFF !important;
}
body, .gradio-container {
    background: #F8FAFF !important;
    color: #1E293B !important;
}
.gradio-container { max-width: 1200px !important; margin: auto !important; }
footer { display: none !important; }
label, .label-wrap span, .svelte-1gfkn6j {
    color: #1E3A8A !important;
}
.block, .form {
    background: #FFFFFF !important;
    border-color: #BFDBFE !important;
}
input, select, textarea, .input-wrap {
    background: #FFFFFF !important;
    color: #1E293B !important;
    border-color: #93C5FD !important;
}
.radio-group label, .checkbox-group label {
    color: #1E293B !important;
}
/* PDF 다운로드 링크 스타일 */
.pdf-download-link a {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #EFF6FF;
    border: 2px solid #3B82F6;
    border-radius: 10px;
    padding: 12px 20px;
    color: #1D4ED8 !important;
    font-size: 15px;
    font-weight: bold;
    text-decoration: none;
    transition: background 0.2s;
}
.pdf-download-link a:hover {
    background: #DBEAFE;
}

/* ── 모든 라디오 버튼을 네모 체크박스 스타일로 ── */
input[type="radio"] {
    -webkit-appearance: none !important;
    appearance: none !important;
    width: 17px !important;
    height: 17px !important;
    border: 2px solid #93C5FD !important;
    border-radius: 3px !important;
    background: white !important;
    cursor: pointer !important;
    position: relative !important;
    flex-shrink: 0 !important;
    display: inline-block !important;
    vertical-align: middle !important;
    margin-top: 1px !important;
    transition: background 0.15s, border-color 0.15s !important;
}
input[type="radio"]:checked {
    background: #2563EB !important;
    border-color: #1D4ED8 !important;
}
input[type="radio"]:checked::after {
    content: "" !important;
    display: block !important;
    position: absolute !important;
    left: 3px !important;
    top: 0px !important;
    width: 5px !important;
    height: 9px !important;
    border: 2.5px solid white !important;
    border-top: none !important;
    border-left: none !important;
    transform: rotate(45deg) !important;
}
input[type="radio"]:hover {
    border-color: #2563EB !important;
}

/* ── 체크박스도 동일한 네모 스타일 통일 ── */
input[type="checkbox"] {
    -webkit-appearance: none !important;
    appearance: none !important;
    width: 17px !important;
    height: 17px !important;
    border: 2px solid #93C5FD !important;
    border-radius: 3px !important;
    background: white !important;
    cursor: pointer !important;
    position: relative !important;
    flex-shrink: 0 !important;
    display: inline-block !important;
    vertical-align: middle !important;
    margin-top: 1px !important;
    transition: background 0.15s, border-color 0.15s !important;
}
input[type="checkbox"]:checked {
    background: #2563EB !important;
    border-color: #1D4ED8 !important;
}
input[type="checkbox"]:checked::after {
    content: "" !important;
    display: block !important;
    position: absolute !important;
    left: 3px !important;
    top: 0px !important;
    width: 5px !important;
    height: 9px !important;
    border: 2.5px solid white !important;
    border-top: none !important;
    border-left: none !important;
    transform: rotate(45deg) !important;
}
input[type="checkbox"]:hover {
    border-color: #2563EB !important;
}

/* ── 성별 라디오 가로 한 줄 배치 ── */
.gender-radio .wrap {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 8px !important;
    align-items: center !important;
}
.gender-radio .wrap label {
    white-space: nowrap !important;
}

/* ── MBTI 드롭다운 폰트 가독성 개선 ── */
.gradio-dropdown input,
.gradio-dropdown .svelte-select,
.gradio-dropdown [data-testid="dropdown-select"] {
    font-size: 15px !important;
    font-weight: 600 !important;
    font-family: 'Apple SD Gothic Neo', 'Nanum Gothic', 'Malgun Gothic', sans-serif !important;
    color: #1E3A8A !important;
    letter-spacing: 0.5px !important;
}
ul[role="listbox"] li {
    font-size: 15px !important;
    font-weight: 600 !important;
    font-family: 'Apple SD Gothic Neo', 'Nanum Gothic', 'Malgun Gothic', sans-serif !important;
    color: #1E293B !important;
    letter-spacing: 0.5px !important;
    padding: 8px 12px !important;
}
ul[role="listbox"] li:hover {
    background: #DBEAFE !important;
    color: #1D4ED8 !important;
}
"""

with gr.Blocks(title="AI 국내 여행 도우미", theme=gr.themes.Soft(), css=CSS) as demo:
    gr.Markdown("# 🗺️ AI 국내 여행 도우미\n> MBTI 기반 여행지 추천 + 일정 자동 생성 + PDF 다운로드")

    with gr.Row(equal_height=False):
        # ── 왼쪽: 입력 ─────────────────────────────────────────────────────
        with gr.Column(scale=1, min_width=360):

            # STEP 1
            gr.Markdown("### 👥 STEP 1. 여행 멤버")
            count = gr.Dropdown(
                choices=list(range(1, MAX_MEMBERS + 1)),
                value=1,
                label="인원 수 선택 (최대 15명)",
            )

            rows, mbtis, genders, ages = [], [], [], []
            for i in range(MAX_MEMBERS):
                with gr.Row(visible=(i == 0)) as row:
                    mbti_label = f"멤버{i+1} MBTI" if i < 2 else f"멤버{i+1} MBTI (선택)"
                    mbti   = gr.Dropdown(choices=MBTI_LIST, label=mbti_label, scale=1)
                    gender = gr.Radio(choices=["남", "여"], value="남",
                                      label="성별", scale=1, elem_classes=["gender-radio"])
                    age    = gr.Number(label="나이", precision=0, scale=1, minimum=0)
                rows.append(row)
                mbtis.append(mbti)
                genders.append(gender)
                ages.append(age)

            # STEP 2
            gr.Markdown("### 📅 STEP 2. 여행 기간")
            duration = gr.Radio(choices=DURATIONS, value="1박2일", label="여행 기간")
            custom_days = gr.Number(
                label="여행 일수 입력 (5일 이상)",
                minimum=5,
                maximum=30,
                precision=0,
                value=5,
                visible=False,
            )

            # STEP 3
            gr.Markdown("### 📍 STEP 3. 지역 또는 테마 *(하나 이상 필수)*")
            province_input = gr.Dropdown(
                choices=REGION_PROVINCES,
                value="(필수 선택)",
                label="① 도/광역시 선택",
            )
            city_input = gr.Dropdown(
                choices=["(선택 사항)"],
                value="(선택 사항)",
                label="② 시/군 선택 (선택 사항)",
                visible=True,
            )
            themes_input = gr.CheckboxGroup(choices=THEMES, label="테마 선택 (최대 2개)")

            btn = gr.Button("✈️  추천 + 일정 생성하기", variant="primary", size="lg")

        # ── 오른쪽: 결과 ────────────────────────────────────────────────────
        with gr.Column(scale=1, min_width=500):
            gr.Markdown("### 🎯 추천 결과 & 여행 일정")
            rec_output   = gr.HTML("<p style='color:#1E40AF'>← 왼쪽 정보를 모두 입력하고 버튼을 눌러주세요!</p>")
            sched_output = gr.HTML("")
            pdf_link_output = gr.HTML("")
            pdf_output   = gr.File(
                label="📥 일정표 PDF (다운로드)",
                visible=False,
                file_types=[".pdf"],
            )

    # ── 이벤트 ──────────────────────────────────────────────────────────────
    count.change(fn=update_rows_count, inputs=[count], outputs=rows)
    province_input.change(fn=update_city_dropdown, inputs=[province_input], outputs=[city_input])
    duration.change(fn=toggle_custom_days, inputs=[duration], outputs=[custom_days])
    themes_input.change(fn=limit_themes, inputs=[themes_input], outputs=[themes_input])

    member_inputs = []
    for i in range(MAX_MEMBERS):
        member_inputs.extend([mbtis[i], genders[i], ages[i]])

    btn.click(
        fn=run_all,
        inputs=[count] + member_inputs + [duration, custom_days, province_input, city_input, themes_input],
        outputs=[rec_output, sched_output, pdf_link_output, pdf_output],
    )

if __name__ == "__main__":
    import tempfile
    demo.launch(allowed_paths=[tempfile.gettempdir()])
