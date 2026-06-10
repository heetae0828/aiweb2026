---
title: AI 국내 여행지 추천
emoji: 🗺️
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
---

# 🗺️ AI 국내 여행 도우미

MBTI 기반 국내 여행지 추천 + 일정 자동 생성 + PDF 다운로드 서비스

---

## 📋 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [주요 기능](#2-주요-기능)
3. [기술 스택](#3-기술-스택)
4. [아키텍처](#4-아키텍처)
5. [디렉토리 구조](#5-디렉토리-구조)
6. [데이터 흐름](#6-데이터-흐름)
7. [로컬 실행](#7-로컬-실행)
8. [HuggingFace Spaces 배포](#8-huggingface-spaces-배포)
9. [환경 변수](#9-환경-변수)

---

## 1. 프로젝트 개요

사용자의 MBTI·성별·나이 조합을 분석하여 국내 여행지 TOP 3를 추천하고,  
선택한 기간에 맞는 시간대별 여행 일정을 자동으로 생성하는 AI 웹 애플리케이션입니다.

단일 페이지(탭 없음) 레이아웃으로 왼쪽에서 조건을 입력하면 오른쪽에 결과가 즉시 표시됩니다.

---

## 2. 주요 기능

| 기능 | 설명 |
|------|------|
| **MBTI 여행지 추천** | 최대 4인 멤버의 MBTI·성별·나이를 종합 분석해 국내 여행지 TOP 3 추천 |
| **주소 + 지도 연동** | 각 추천지의 실제 주소를 제공하며, 클릭 시 네이버맵에서 바로 확인 가능 |
| **MBTI 조합 분석** | 멤버 조합의 여행 스타일을 재미있게 풀어주는 맞춤 분석 텍스트 제공 |
| **여행 꿀팁** | 해당 여행지·멤버 구성에 맞는 실용 팁 3가지 제공 |
| **일정 자동 생성** | 선택한 기간(당일치기~4박5일)에 맞춰 일차별 시간대별 일정표 자동 생성 |
| **지역 2단계 선택** | 도/광역시 선택 후 시/군 세부 선택 가능 (서울/경기/인천, 강원, 충청, 전라, 경상, 제주) |
| **PDF 다운로드** | 생성된 일정표를 한글 폰트 적용 PDF로 다운로드 (파일명 클릭으로 즉시 저장) |

---

## 3. 기술 스택

| 영역 | 기술 |
|------|------|
| **언어** | Python 3.12 |
| **UI 프레임워크** | Gradio 6.x (`gr.Blocks`, `gr.HTML`, `gr.File`) |
| **AI 모델** | Qwen/Qwen2.5-72B-Instruct (HuggingFace Inference API) |
| **PDF 생성** | Matplotlib (한글 폰트: NanumGothic / Apple SD Gothic Neo) |
| **지도 연동** | 네이버맵 검색 URL (`map.naver.com/p/search/`) |
| **환경 관리** | python-dotenv |
| **배포 플랫폼** | HuggingFace Spaces |

---

## 4. 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    Gradio Web UI                        │
│                                                         │
│  ┌──────────────────┐      ┌──────────────────────────┐ │
│  │   입력 패널 (좌)  │      │     결과 패널 (우)        │ │
│  │                  │      │                          │ │
│  │  STEP 1. 멤버    │      │  • 추천 TOP 3            │ │
│  │  (MBTI/성별/나이) │ ───► │    + 주소 (네이버맵 링크) │ │
│  │                  │      │  • MBTI 조합 분석         │ │
│  │  STEP 2. 기간    │      │  • 여행 꿀팁              │ │
│  │  (당일~4박5일)   │      │  • 일정표 (일차별 HTML)   │ │
│  │                  │      │  • PDF 다운로드 링크      │ │
│  │  STEP 3. 지역/   │      │                          │ │
│  │  ① 도/광역시     │      └──────────────────────────┘ │
│  │  ② 시/군 (연동)  │                                   │
│  │  + 테마 선택     │                                   │
│  └──────────────────┘                                   │
└───────────────────────┬─────────────────────────────────┘
                        │ run_all()
                        ▼
┌─────────────────────────────────────────────────────────┐
│                  비즈니스 로직                            │
│                                                         │
│  _build_prompt()  →  구조화된 JSON 프롬프트 생성          │
│                                                         │
│  HuggingFace API (Qwen2.5-72B-Instruct)                 │
│    └─ 단일 호출로 추천 + 일정 동시 반환 (JSON)            │
│                                                         │
│  _schedule_html()  →  일차별 HTML 테이블 렌더링           │
│  _make_pdf()       →  matplotlib으로 PDF 파일 생성       │
└─────────────────────────────────────────────────────────┘
```

### 핵심 설계 결정

- **단일 API 호출**: 추천과 일정을 분리된 두 번의 API 호출 대신, 하나의 구조화된 JSON 프롬프트로 모든 결과를 한 번에 수신합니다.
- **지역 2단계 선택**: `REGION_TREE` 딕셔너리로 도/광역시 → 시/군 계층을 관리. 상위 선택 시 하위 드롭다운이 동적으로 갱신됩니다.
- **서버사이드 PDF**: 브라우저 인쇄 대신 matplotlib으로 서버에서 PDF를 생성해 한글 폰트와 레이아웃을 완전히 제어합니다.
- **네이버맵 딥링크**: 주소를 URL 인코딩(`urllib.parse.quote`)하여 `map.naver.com/p/search/{주소}` 형태로 직접 연결합니다.

---

## 5. 디렉토리 구조

```
aiweb2026/
├── app.py              # 메인 애플리케이션 (UI + 비즈니스 로직 통합)
├── requirements.txt    # 의존성 패키지
├── .env                # 로컬 환경 변수 (HF_TOKEN)
├── .gitignore          # .env, .venv, __pycache__ 제외
└── README.md           # 이 문서
```

`app.py` 내부 주요 함수:

| 함수 | 역할 |
|------|------|
| `update_rows()` | 인원 수 변경 시 멤버 입력 행 show/hide |
| `update_city_dropdown()` | 도/광역시 선택 시 시/군 드롭다운 동적 갱신 |
| `_build_prompt()` | 멤버 정보·조건을 바탕으로 AI 프롬프트 생성 |
| `_schedule_html()` | AI 응답의 schedule JSON → 일차별 HTML 테이블 |
| `_make_pdf()` | schedule JSON → matplotlib PDF 파일 |
| `run_all()` | 전체 파이프라인 실행 (유효성 검사 → API 호출 → 렌더링) |

---

## 6. 데이터 흐름

```
사용자 입력
  (MBTI, 성별, 나이 × n명 / 여행기간 / 도·시군 / 테마)
        │
        ▼
  run_all() — 입력 유효성 검사 + 지역 결정 (시군 우선 → 도 fallback)
        │
        ▼
  _build_prompt() — JSON 스키마 포함 프롬프트 생성
        │
        ▼
  HuggingFace API (Qwen2.5-72B-Instruct)
        │  응답 (순수 JSON)
        ▼
  JSON 파싱 (json.loads + 정규식 클렌징)
        │
        ├──► 추천 영역
        │      └─ TOP3 카드 + 주소 + 네이버맵 링크
        │
        ├──► 일정 영역 (_schedule_html)
        │      └─ 1일차/2일차... HTML 테이블
        │
        └──► PDF 영역 (_make_pdf)
               └─ matplotlib → /tmp/travel_*.pdf
                  → HTML 다운로드 링크 + gr.File 백업
```

---

## 7. 로컬 실행

### 사전 요구사항

- Python 3.10 이상
- HuggingFace API 토큰 (`HF_TOKEN`)

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/heetae0828/aiweb2026.git
cd aiweb2026

# 2. 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
echo "HF_TOKEN=hf_..." > .env

# 5. 실행
python app.py
```

브라우저에서 `http://localhost:7860` 접속

### 한글 PDF 폰트

로컬 macOS 환경에서는 NanumGothic 또는 Apple SD Gothic Neo 폰트를 자동 탐색합니다.  
Linux 환경(HuggingFace Spaces)에서는 아래와 같이 설치합니다:

```bash
apt-get install -y fonts-nanum
```

---

## 8. HuggingFace Spaces 배포

### 배포 절차

```bash
# HuggingFace Spaces 저장소에 푸시
git remote add space https://huggingface.co/spaces/<username>/<space-name>
git push space main
```

### API 키 등록

HuggingFace Spaces는 `.env` 파일을 지원하지 않으므로 **Repository Secrets**를 사용합니다.

```
Spaces > Settings > Repository secrets > New secret
  Name : HF_TOKEN
  Value: hf_...
```

앱 코드에서 `os.getenv("HF_TOKEN")`으로 읽기 때문에 별도 코드 수정 없이 동작합니다.

---

## 9. 환경 변수

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `HF_TOKEN` | ✅ | HuggingFace API 토큰. Qwen2.5-72B-Instruct 모델 호출에 사용 |

---

> 재미로 보는 MBTI 여행 추천 서비스입니다. AI 응답은 참고용이며 실제 교통·운영 정보는 반드시 현지 확인 바랍니다.
