# 10주차 — 칼로리카운터 Oracle 배포 + GitHub Actions CI/CD

본인 칼로리카운터를 Oracle Always Free 서버에 Docker로 띄우고, `git push` 한 번으로 자동 배포되는 CI/CD를 만든다. 9주차 페이지의 "Live Demo (Coming Week 10)" 버튼을 본인 데모로 연결하면 마무리.

수업 자료는 [`10_week10.html`](10_week10.html)을 브라우저로 열어 본다.

---

## 폴더 구조

```
week10/
├── 10_week10.html              ← 수업 자료 (브라우저로 열기)
├── README.md                   ← 이 파일
├── week10_calorie.zip          ← Oracle 서버에 업로드할 zip
├── week10_calorie/             ← zip 풀어둔 사본 (참고용)
│   ├── app.py
│   ├── model_config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── nginx-calorie.conf
│   ├── .gitignore
│   └── .github/workflows/deploy.yml
└── images/week10/              ← 수업 자료에 들어가는 스크린샷
```

---

## 실습 전 손에 있어야 하는 것

| 항목 | 어디서 |
|------|------|
| 본인 OCI 인스턴스 RUNNING + Public IP | 9주차 숙제 결과 |
| SSH 키 파일 (`~/.ssh/oracle_key`) | 9주차에 받은 그대로 |
| Hugging Face Read 토큰 (`hf_...`) | 6주차에 발급한 그대로 (없으면 https://huggingface.co/settings/tokens) |
| 본인 GitHub 계정 | 9주차 그대로 |
| `week10_calorie.zip` | e-class 또는 이 폴더 |
| 분배 시트 본인 행 위치 | [분배 시트 열기](https://docs.google.com/spreadsheets/d/1pDMyc5JPKs-61l5W0Vujw99z-HetFYmMjtWVj03ZiD4/edit?usp=sharing) |

OCI 가입을 못한 학생은 시트 본인 행에 강사가 안내하는 공유 IP를 일단 입력. 추후 본인 가입 완료되면 D 컬럼만 본인 IP로 갱신하면 5분 내 자동 반영.

---

## 빠른 시작 체크리스트

수업 자료 [`10_week10.html`](10_week10.html)의 두 단계 흐름을 그대로 따른다.

### STAGE 1 — 수동 배포 (한 번 띄우기)

- [ ] § 1. 시트 D 컬럼에 본인 Public IP 입력
- [ ] § 2-1. SSH 접속 (`ssh -i ~/.ssh/oracle_key ubuntu@<IP>`)
- [ ] § 2-2. swap 2GB 추가 (`free -h`로 확인)
- [ ] § 2-3. iptables INPUT에 80/443 ALLOW (REJECT 위에 INSERT)
- [ ] § 2-4. OCI Console에서 Default Security List에 80/443 ingress 추가
- [ ] § 3-1. Docker 설치 (`docker compose version` 통과)
- [ ] § 3-2. zip을 서버에 업로드 (`scp ... :~/`)
- [ ] § 3-3. `unzip ~/week10_calorie.zip -d ~/calorie`
- [ ] § 3-4. `.env`에 HF_TOKEN 입력 + `chmod 600 .env`
- [ ] § 3-5. `docker compose up -d --build` → `curl -I http://127.0.0.1:7860` 200 OK
- [ ] § 4-2. nginx-calorie.conf의 `__STUDENT_ID__`를 본인 ID로 치환
- [ ] § 4-3. `https://<본인_ID>-demo.aiweb2026.site` 접속 → 자물쇠 + Gradio UI 확인

### STAGE 2 — 자동 배포 (이후 push만)

- [ ] § 5-1. GitHub에 `my-calorie-counter` 리포 생성 (Public)
- [ ] § 5-2. zip 내용 복사 후 `git push` (`.env` 제외 확인!)
- [ ] § 5-3. Secret 4개 등록 — `SSH_HOST`, `SSH_USER`, `SSH_KEY`, `HF_TOKEN`
- [ ] § 6-1. `app.py` 한 글자 수정 + `git push`
- [ ] § 6-2. Actions 탭 그린 체크 + 본인 사이트 새로고침으로 변경 확인

### 마무리

- [ ] § 7-1. 9주차 페이지 `index.html`의 "Live Demo" 버튼을 본인 도메인으로 교체 + push
- [ ] § 7-3. 동료 1명 사이트의 Live Demo 버튼 작동 확인 + 댓글 한 줄

---

## 수업 후 손에 남는 것

- `https://<본인_ID>-demo.aiweb2026.site` — 24시간 떠 있는 본인 칼로리카운터
- `github.com/<본인>/my-calorie-counter` — Public 리포 + CI/CD
- `git push` 한 번이 30초 안에 사이트 반영되는 자동화
- 9주차 페이지 "Live Demo" 버튼이 살아 있는 상태

면접에서 "AI 웹 프로젝트 만들어봤어요"라고 했을 때 줄 수 있는 URL.

---

## 막혔을 때

수업 자료 [`10_week10.html`](10_week10.html) § 8 "자주 막히는 함정 모음" 표를 먼저 확인. 거기 없는 증상이면 옆 학생과 화면 공유 → 강사 호출.
