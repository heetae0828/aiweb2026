"""
AI 국내 여행 도우미 (단일 페이지)
MBTI 여행지 추천 + 1일차/2일차별 일정표 + PDF 다운로드
"""
import json
import os
import re
import tempfile
import urllib.parse
import urllib.request
from datetime import date, timedelta

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

# ── 네이버 로컬 검색 ────────────────────────────────────────────────────────
_NAVER_FOOD_QUERIES = {
    "아침":     ["{r} 아침식사 맛집", "{r} 조식", "{r} 해장국"],
    "점심":     ["{r} 점심 맛집", "{r} 맛집", "{r} 한식"],
    "저녁":     ["{r} 저녁 맛집", "{r} 고기집", "{r} 해산물"],
    "카페":     ["{r} 카페", "{r} 분위기 카페", "{r} 디저트"],
    "분위기맛집": ["{r} 분위기 맛집", "{r} 뷰 맛집", "{r} 이색 레스토랑"],
}


def _extract_place_id(raw_link: str) -> str | None:
    """네이버 API link 필드에서 place ID 추출. 없으면 None.
    Naver Local Search API link는 가게 홈페이지 URL이므로 place ID가 없는 경우가 대부분."""
    if not raw_link:
        return None
    # map.naver.com/local/siteview.nhn?code=XXXXXXXX 형태
    m = re.search(r"code=(\d+)", raw_link)
    if m:
        return m.group(1)
    # map.naver.com/p/entry/place/XXXXXXXX 형태
    m = re.search(r"/place/(\d+)", raw_link)
    return m.group(1) if m else None


def _naver_local_search(query: str, client_id: str, client_secret: str, display: int = 5) -> list:
    """네이버 로컬 검색 API - sort=comment(리뷰순=상위 노출 기준)."""
    url = (
        "https://openapi.naver.com/v1/search/local.json"
        f"?query={urllib.parse.quote(query)}&display={display}&sort=comment"
    )
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    })
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read()).get("items", [])
    except Exception:
        return []


def _search_naver_restaurants(region: str, client_id: str, client_secret: str) -> dict:
    import concurrent.futures

    global_seen: set = set()  # 카테고리 간 전역 중복 제거

    def fetch_cat(args):
        cat, query_tmpls = args
        items = []
        for tmpl in query_tmpls:
            if len(items) >= 10:
                break
            q = tmpl.format(r=region)
            for raw in _naver_local_search(q, client_id, client_secret, display=5):
                name     = re.sub(r"<[^>]+>", "", raw.get("title", "")).strip()
                addr     = raw.get("roadAddress", "") or raw.get("address", "")
                raw_link = raw.get("link", "")
                place_id = _extract_place_id(raw_link)

                if not name:
                    continue
                key = name + addr
                if key in global_seen:
                    continue
                global_seen.add(key)

                # place ID 있으면 직접 링크, 없으면 이름으로 검색
                if place_id:
                    place_url = f"https://map.naver.com/p/entry/place/{place_id}"
                else:
                    place_url = f"https://map.naver.com/p/search/{urllib.parse.quote(name)}"
                items.append({
                    "name":      name,
                    "address":   addr,
                    "desc":      raw.get("category", ""),
                    "price":     "",
                    "place_url": place_url,
                })
        return cat, items[:10]

    result = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_cat, (cat, tmpls)): cat
                   for cat, tmpls in _NAVER_FOOD_QUERIES.items()}
        for future in concurrent.futures.as_completed(futures, timeout=25):
            try:
                cat, items = future.result()
                result[cat] = items
            except Exception:
                result[futures[future]] = []
    return result


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
    food_rule = ""
    # 맛집은 AI 대신 네이버 로컬 API로 검색하므로 프롬프트에서 제외

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

    mbti_summary = ", ".join(m[0] for m in members if m[0]) or "미입력"
    gender_age   = " / ".join(f"{m[1]} {int(m[2])}세" for m in members)
    region_str   = region if region and region not in ("(필수 선택)", "(선택 사항)") else "미지정"
    themes_str   = ", ".join(themes) if themes else "없음"

    schedule_schema = "\n".join(
        f'    "{i+1}일차": [\n'
        f'      {{"시간":"09:00","장소":"장소명","활동":"활동명","상세내용":"구체적인 설명 2문장","이동수단":"이동수단"}},\n'
        f'      ...\n'
        f'    ]'
        for i in range(n_days)
    )

    return f"""[역할]
당신은 대한민국 국내여행 전문 큐레이터입니다.
MBTI 심리학과 지역 여행 트렌드를 결합해, 여행자 성향에 딱 맞는 구체적이고 실현 가능한 여행 계획을 제안합니다.

[여행자 정보]
- 인원: {len(members)}명
- MBTI: {mbti_summary}
- 성별/나이: {gender_age}
- 각 MBTI 성향:
{member_lines}

[여행 조건]
- 기간: {duration_label} (총 {n_days}일, 숙박 {n_days-1}박)
- 희망 지역: {region_str}
- 선호 테마: {themes_str}

[출력 형식]
반드시 아래 JSON 구조만 출력하세요. 마크다운 코드블록(`````), 설명 텍스트 절대 금지.

{{
  "top_destination": "최종 선정 여행지명 (예: 전주, 강릉, 제주 동부)",
  "trip_concept": "이번 여행 컨셉을 15자 이내로 (예: 전주 골목 감성 완전 정복, 강릉 바다+커피 힐링)",
  "recommendations": [
    {{
      "rank": 1,
      "name": "여행지명 (구/동 단위까지)",
      "address": "실제 도로명주소",
      "reason": "이 MBTI 조합이 이 여행지를 좋아하는 이유를 구체적으로 2~3문장"
    }},
    {{"rank": 2, "name": "...", "address": "...", "reason": "..."}},
    {{"rank": 3, "name": "...", "address": "...", "reason": "..."}}
  ],
  "mbti_analysis": "멤버들의 MBTI 조합이 만들어내는 여행 시너지와 주의할 갈등 포인트를 재미있고 현실적으로 3~4문장",
  "tips": [
    "이 지역+이 MBTI 조합에 특화된 실용 팁 (교통, 예약, 시간대 등)",
    "팁2",
    "팁3"
  ],
  "schedule": {{
{schedule_schema}
  }}{stay_schema}
}}

[일정 작성 필수 규칙]
1. 매 일차 오전 기상(07:00~09:00)부터 취침 전(21:00~23:00)까지 빈 시간 없이 작성
2. 식사(아침/점심/저녁), 이동, 관광, 휴식, 숙박 체크인 모두 포함
3. 동선 규칙: 지리적으로 한 방향으로만 이동 (A→B→C→D). 같은 지점 왕복 절대 금지
4. 하루 안에서 한 동네를 깊게 탐방하거나, 자연스럽게 인접 지역으로 이동하는 흐름으로 구성
5. 장소명은 실제 존재하는 명칭 사용 (관광지, 거리, 시장 등 실제 이름)
6. 상세내용은 "왜 이곳인지 + 무엇을 할 수 있는지" 2문장으로 구체적으로 작성{stay_rule}
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

    # 선택된 지역 결정 — 도/광역시만 선택한 경우 랜덤 시/군 선택
    import random
    region = ""
    if city and city not in ("(선택 사항)", None):
        region = city
    elif province and province not in ("(필수 선택)", None):
        cities = REGION_TREE.get(province, [])
        if cities:
            region = random.choice(cities)  # 매번 다른 시/군 추천
        else:
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
                    "당신은 대한민국 국내여행 큐레이터입니다. 다음 규칙을 반드시 지키세요:\n"
                    "1. 출력은 순수 JSON만. 마크다운 코드블록(```)이나 설명 텍스트 절대 금지.\n"
                    "2. JSON 키 이름을 절대 바꾸지 마세요. 요청한 구조 그대로 출력.\n"
                    "3. 장소명은 실제 존재하는 곳만 사용. 창작 금지.\n"
                    "4. 일정은 시간 순서대로, 빈 시간 없이 촘촘하게 작성.\n"
                    "5. 동선은 지리적으로 한 방향 흐름 유지. 왕복 이동 금지.\n"
                    "6. MBTI 분석은 실제 심리학 기반으로 재미있고 공감 가능하게."
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

        # ── 네이버 로컬 API로 실제 맛집 검색 (항상 실행) ─────────────────
        naver_restaurants = {}
        naver_id     = os.getenv("NAVER_CLIENT_ID", "")
        naver_secret = os.getenv("NAVER_CLIENT_SECRET", "")
        if naver_id and naver_secret:
            search_region = region or top_dest
            yield _loading_html("🍽️ 네이버에서 실제 맛집·카페를 검색하는 중...", 6), "", "", gr.update(visible=False, value=None)
            naver_restaurants = _search_naver_restaurants(search_region, naver_id, naver_secret)

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
            n_nights = n_days - 1
            checkin_date  = date.today() + timedelta(days=1)
            checkout_date = checkin_date + timedelta(days=n_nights)
            checkin_str  = checkin_date.strftime("%Y-%m-%d")
            checkout_str = checkout_date.strftime("%Y-%m-%d")

            def _yeogi_url(keyword, ci=checkin_str, co=checkout_str):
                kw = urllib.parse.quote(keyword)
                return (f"https://www.yeogi.com/domestic-accommodations"
                        f"?keyword={kw}&checkIn={ci}&checkOut={co}"
                        f"&personal={actual_count}&typoCorrect=true&nonAffiliated=true")

            rec_html += f"""
<hr style="border:none;border-top:1px solid #E5E7EB;margin:16px 0">
<h2 style="color:#1D4ED8">🏨 숙소 예약</h2>
<p style="font-size:13px;color:#6B7280;margin-bottom:10px">
  {actual_count}명 · {checkin_str} ~ {checkout_str} ({n_nights}박) 기준으로 검색합니다.
</p>
<div style="margin-bottom:12px">
  <a href="{_yeogi_url(top_dest)}" target="_blank"
     style="background:#FF5A5F;color:white;padding:10px 18px;border-radius:8px;
            text-decoration:none;font-weight:bold;font-size:14px">
    🏠 여기어때에서 찾기
  </a>
</div>"""
            # AI 추천 숙소 목록 (다중 지역이면 날짜 분배)
            accommodations = data.get("accommodation", [])
            if accommodations:
                rec_html += '<div style="display:flex;flex-direction:column;gap:8px">'
                for idx, acc in enumerate(accommodations):
                    # 숙소마다 체크인 날짜를 일차 순서로 배분
                    acc_ci = (checkin_date + timedelta(days=idx)).strftime("%Y-%m-%d")
                    acc_co = (checkin_date + timedelta(days=idx + 1)).strftime("%Y-%m-%d")
                    # 마지막 숙소는 checkout까지
                    if idx == len(accommodations) - 1:
                        acc_co = checkout_str
                    acc_keyword = f"{acc.get('name','')} {acc.get('area','')}"
                    yeogi_acc = _yeogi_url(acc_keyword, acc_ci, acc_co)
                    rec_html += f"""
<div style="background:#FFF5F5;border-left:4px solid #FF5A5F;padding:10px 14px;border-radius:0 8px 8px 0">
  <div style="font-weight:bold;font-size:14px;margin-bottom:2px">
    🏨 {acc.get('name','')} <span style="color:#6B7280;font-weight:normal;font-size:12px">({acc.get('area','')} · {acc.get('type','')})</span>
  </div>
  <div style="font-size:12px;color:#6B7280;margin-bottom:4px">체크인 {acc_ci} → 체크아웃 {acc_co}</div>
  <div style="font-size:13px;color:#374151;margin-bottom:6px">1박 {acc.get('price_per_night','')}</div>
  <a href="{yeogi_acc}" target="_blank"
     style="font-size:12px;color:#FF5A5F;text-decoration:none">여기어때에서 검색 →</a>
</div>"""
                rec_html += '</div>'

        # ── 맛집 리스트 (네이버 로컬 API 결과 항상 표시) ──────────────────
        if True:
            restaurants = naver_restaurants if naver_restaurants else {}
            # 맛집 탐방 테마: 5개 카테고리 전부 + 더보기
            # 일반: 점심·저녁·카페 3개만, 각 3개씩만 표시
            if is_food:
                cat_icons = {"아침": "🌅", "점심": "☀️", "저녁": "🌙", "카페": "☕", "분위기맛집": "✨"}
            else:
                cat_icons = {"점심": "☀️", "저녁": "🌙", "카페": "☕"}

            if not naver_id or not naver_secret:
                rec_html += """
<hr style="border:none;border-top:1px solid #E5E7EB;margin:16px 0">
<div style="background:#FEF3C7;border:1px solid #F59E0B;border-radius:8px;padding:12px 16px;font-size:13px;color:#92400E">
  ⚠️ <b>NAVER_CLIENT_ID / NAVER_CLIENT_SECRET</b> 환경변수가 설정되지 않아 맛집 검색을 건너뜁니다.<br>
  HuggingFace Spaces → Settings → Repository secrets 에서 등록해주세요.
</div>"""
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
                        name      = item.get("name", "")
                        addr      = item.get("address", "")
                        desc      = item.get("desc", "")
                        price     = item.get("price", "")
                        place_url = item.get("place_url") or f"https://map.naver.com/p/search/{urllib.parse.quote(name)}"
                        return f"""<div style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:8px;padding:10px 12px">
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px">
    <span style="font-weight:bold;font-size:13.5px;color:#1E293B">{name}</span>
    <a href="{place_url}" target="_blank"
       style="display:inline-flex;align-items:center;gap:4px;background:#03C75A;color:white;
              font-size:11px;font-weight:bold;padding:3px 8px;border-radius:4px;
              text-decoration:none;white-space:nowrap;flex-shrink:0">
      <span style="font-weight:900;font-size:13px">N</span> 네이버 플레이스
    </a>
  </div>
  <div style="font-size:12px;color:#6B7280;margin-bottom:3px">📍 {addr}</div>
  <div style="font-size:12.5px;color:#374151;margin-bottom:3px">{desc}</div>
  {"<div style='font-size:12px;font-weight:bold;color:#B45309'>"+price+"</div>" if price else ""}
</div>"""

                    if is_food:
                        # 맛집 탐방: 3개 보여주고 더보기
                        shown = items[:3]
                        hidden = items[3:]
                    else:
                        # 일반: 3개만 표시, 더보기 없음
                        shown = items[:3]
                        hidden = []

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
