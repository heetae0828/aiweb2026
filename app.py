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

# ── 상수 ────────────────────────────────────────────────────────────────────
MBTI_LIST = [
    "ISTJ", "ISFJ", "INFJ", "INTJ",
    "ISTP", "ISFP", "INFP", "INTP",
    "ESTP", "ESFP", "ENFP", "ENTP",
    "ESTJ", "ESFJ", "ENFJ", "ENTJ",
]
REGIONS = [
    "(선택 안 함)",
    "서울", "경기", "인천",
    "강릉", "속초", "평창", "춘천",
    "대전", "청주", "공주", "충주",
    "전주", "광주", "여수", "순천", "목포",
    "부산", "대구", "경주", "안동", "통영", "거제",
    "제주시", "서귀포",
]
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
def update_rows(count: int):
    return [gr.update(visible=(i < int(count))) for i in range(4)]


# ── 통합 프롬프트 ────────────────────────────────────────────────────────────
def _build_prompt(members, duration, region, themes):
    n_days = DURATION_DAYS.get(duration, 1)
    member_lines = "\n".join(
        f"  - 멤버{i+1}: MBTI={m[0]} ({MBTI_TRAITS.get(m[0], '')}), 성별={m[1]}, 나이={int(m[2])}세"
        for i, m in enumerate(members)
    )
    region_line = f"선호 지역: {region}" if region and region != "(선택 안 함)" else "지역 무관"
    themes_line = f"선호 테마: {', '.join(themes)}" if themes else "테마 무관"
    schedule_keys = ", ".join(f'"{i+1}일차": [...]' for i in range(n_days))

    return f"""당신은 국내 여행 전문가이자 MBTI 전문가입니다.
아래 정보를 바탕으로 여행지 추천과 상세 일정을 하나의 JSON으로 작성해주세요.

[여행 멤버]
{member_lines}

[여행 조건]
- 여행 기간: {duration} (총 {n_days}일)
- {region_line}
- {themes_line}

반드시 순수 JSON만 출력하세요 (마크다운 코드블록 없이):
{{
  "top_destination": "1위 여행지명",
  "recommendations": [
    {{"rank": 1, "name": "여행지명", "address": "도로명주소 또는 지번주소 (시/군/구/동 포함)", "reason": "MBTI와 연결한 선정 이유 2~3문장"}},
    {{"rank": 2, "name": "여행지명", "address": "도로명주소 또는 지번주소 (시/군/구/동 포함)", "reason": "선정 이유 2~3문장"}},
    {{"rank": 3, "name": "여행지명", "address": "도로명주소 또는 지번주소 (시/군/구/동 포함)", "reason": "선정 이유 2~3문장"}}
  ],
  "mbti_analysis": "MBTI 조합 여행 스타일을 재미있게 3~4문장",
  "tips": ["팁1", "팁2", "팁3"],
  "schedule": {{{schedule_keys}}}
}}

일정 항목 형식:
{{"시간": "HH:MM", "장소": "장소명", "활동": "활동명", "상세내용": "설명 1~2문장", "이동수단": "교통수단"}}

일정 작성 규칙:
- 1시간 단위로 오전부터 마지막 날 저녁 숙박까지 빠짐없이 작성
- 식사(아침/점심/저녁), 이동, 관광, 숙박 모두 포함
- 날짜별로 {schedule_keys.split(':')[0].replace('"','').strip()} 형식 키에 배열 작성
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
    duration, region, themes,
):
    all_data = [
        (mbti1, gender1, age1), (mbti2, gender2, age2),
        (mbti3, gender3, age3), (mbti4, gender4, age4),
    ]
    active = []
    for i in range(int(count)):
        mbti, gender, age = all_data[i]
        if not mbti:
            return f"❌ 멤버{i+1}의 MBTI를 선택해주세요.", "", gr.update(visible=False, value=None)
        if not age or age <= 0:
            return f"❌ 멤버{i+1}의 나이를 입력해주세요.", "", gr.update(visible=False, value=None)
        active.append((mbti, gender, age))

    if (not region or region == "(선택 안 함)") and not themes:
        return "❌ 지역 또는 테마 중 하나 이상 선택해주세요.", "", gr.update(visible=False, value=None)

    api_key = os.getenv("HF_TOKEN", "")
    if not api_key:
        return "❌ HF_TOKEN이 설정되지 않았습니다.", "", gr.update(visible=False, value=None)

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api-inference.huggingface.co/v1/",
        )
        prompt = _build_prompt(active, duration, region, themes)
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-72B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group() if m else raw)

        # 추천 HTML (주소 + 네이버맵 링크 포함)
        recs   = data.get("recommendations", [])
        mbti_a = data.get("mbti_analysis", "")
        tips   = data.get("tips", [])
        medals = ["🥇", "🥈", "🥉"]

        rec_html = '<div style="font-family:\'Apple SD Gothic Neo\',\'Nanum Gothic\',sans-serif">'
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
        rec_html += "</ol></div>"

        # 일정표 HTML
        schedule   = data.get("schedule", {})
        sched_html = _schedule_html(schedule)

        # PDF
        pdf_path = _make_pdf(data)
        top_dest = data.get("top_destination", "여행지")

        if pdf_path:
            filename = os.path.basename(pdf_path)
            pdf_link_html = f'''<div class="pdf-download-link" style="margin-top:16px">
  <a href="/file={pdf_path}" download="{top_dest}_여행일정표.pdf">
    📥 {top_dest}_여행일정표.pdf — 클릭하여 다운로드
  </a>
</div>'''
        else:
            pdf_link_html = ""

        return rec_html, sched_html, pdf_link_html, gr.update(visible=bool(pdf_path), value=pdf_path)

    except json.JSONDecodeError as e:
        return f"<p>❌ 응답 파싱 오류: {e}</p>", "", "", gr.update(visible=False, value=None)
    except Exception as e:
        return f"<p>❌ 오류: {e}</p>", "", "", gr.update(visible=False, value=None)


# ══════════════════════════════════════════════════════════════════════════════
# Gradio UI  (단일 페이지)
# ══════════════════════════════════════════════════════════════════════════════
CSS = """
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
"""

with gr.Blocks(title="AI 국내 여행 도우미") as demo:
    gr.Markdown("# 🗺️ AI 국내 여행 도우미\n> MBTI 기반 여행지 추천 + 일정 자동 생성 + PDF 다운로드")

    with gr.Row(equal_height=False):
        # ── 왼쪽: 입력 ─────────────────────────────────────────────────────
        with gr.Column(scale=1, min_width=360):

            # STEP 1
            gr.Markdown("### 👥 STEP 1. 여행 멤버")
            count = gr.Radio(choices=[1, 2, 3, 4], value=1, label="인원 수")
            rows, mbtis, genders, ages = [], [], [], []
            for i in range(4):
                with gr.Row(visible=(i == 0)) as row:
                    mbti   = gr.Dropdown(choices=MBTI_LIST, label=f"멤버{i+1} MBTI", scale=2)
                    gender = gr.Radio(choices=["남", "여", "미선택"], value="미선택",
                                      label="성별", scale=1)
                    age    = gr.Number(label="나이", precision=0, scale=1)
                rows.append(row)
                mbtis.append(mbti)
                genders.append(gender)
                ages.append(age)

            # STEP 2
            gr.Markdown("### 📅 STEP 2. 여행 기간")
            duration = gr.Radio(choices=DURATIONS, value="1박2일", label="여행 기간")

            # STEP 3
            gr.Markdown("### 📍 STEP 3. 지역 또는 테마 *(하나 이상 필수)*")
            region       = gr.Dropdown(choices=REGIONS, value="(선택 안 함)", label="지역 선택")
            themes_input = gr.CheckboxGroup(choices=THEMES, label="테마 선택")

            btn = gr.Button("✈️  추천 + 일정 생성하기", variant="primary", size="lg")

        # ── 오른쪽: 결과 ────────────────────────────────────────────────────
        with gr.Column(scale=1, min_width=500):
            gr.Markdown("### 🎯 추천 결과 & 여행 일정")
            rec_output   = gr.HTML("<p style='color:#1E40AF'>← 왼쪽 정보를 모두 입력하고 버튼을 눌러주세요!</p>")
            sched_output = gr.HTML("")
            pdf_link_output = gr.HTML("")
            pdf_output   = gr.File(
                label="📥 일정표 PDF (백업 다운로드)",
                visible=False,
                file_types=[".pdf"],
            )

    # ── 이벤트 ──────────────────────────────────────────────────────────────
    count.change(fn=update_rows, inputs=[count], outputs=rows)

    member_inputs = []
    for i in range(4):
        member_inputs.extend([mbtis[i], genders[i], ages[i]])

    btn.click(
        fn=run_all,
        inputs=[count] + member_inputs + [duration, region, themes_input],
        outputs=[rec_output, sched_output, pdf_link_output, pdf_output],
    )

if __name__ == "__main__":
    import tempfile
    demo.launch(theme=gr.themes.Soft(), css=CSS, allowed_paths=[tempfile.gettempdir()])
