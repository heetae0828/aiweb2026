# Walrus Study

Walrus Study는 OpenAI GPT 기반으로 학습 자료에서 문제를 생성하고, 학생 답안을 참고 문서로 채점하는 Gradio 웹 앱입니다.

## 기능
- PDF / TXT / Markdown 학습 자료 업로드
- 자동 문제 생성
- 답안 채점 및 피드백 제공
- 로컬 `history.json`에 채점 기록 저장

## 실행 방법

1. `.env` 파일 생성

```bash
cp .env.example .env
```

2. `OPENAI_API_KEY` 값을 `.env`에 입력

3. 로컬 실행

```bash
pip install -r requirements.txt
python app.py
```

4. 브라우저에서 `http://localhost:7860` 접속

## Docker 사용

```bash
docker build -t walrus-study .
docker run -p 7860:7860 --env-file .env walrus-study
```

## Oracle 서버 배포 준비

1. 루트에 `docker-compose.yml` 파일을 둡니다.
2. 서버에 `.env` 파일을 직접 생성해서 `OPENAI_API_KEY`를 설정합니다.
3. GitHub Actions 배포 시 `SSH_HOST`, `SSH_USER`, `SSH_KEY`를 GitHub Secrets에 등록합니다.

## GitHub Actions 배포

루트 `.github/workflows/deploy.yml`은 Oracle 서버에 SSH로 접속하여 리포지토리를 동기화하고 `docker compose up -d --build`를 실행합니다.
