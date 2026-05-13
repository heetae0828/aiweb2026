# Walrus Study

Walrus Study는 OpenAI GPT API를 활용해 학습 자료 기반 문제를 생성하고 학생 답안을 채점하는 Gradio 앱입니다.

## 실행 방법

1. `.env.example`을 복사해 `.env`를 생성합니다.
2. `OPENAI_API_KEY`를 `.env`에 입력합니다.
3. 의존성을 설치합니다:

```bash
pip install -r requirements.txt
```

4. 로컬 실행:

```bash
python app.py
```

5. 브라우저에서 `http://localhost:7860`에 접속합니다.

## Docker 실행

```bash
docker build -t walrus-study .
docker run -p 7860:7860 --env-file .env walrus-study
```

## HuggingFace Space 배포

1. HF Space를 생성하고 Docker SDK를 선택합니다.
2. GitHub 리포지토리 Secrets에 `HF_TOKEN`을 등록합니다.
3. `.github/workflows/sync-to-hf.yml`의 `HF_USER`와 `HF_SPACE`를 본인 값으로 변경합니다.
4. `main` 브랜치에 push하면 자동으로 HF Space로 동기화됩니다.

## 주의

- `.env`에는 `OPENAI_API_KEY`를 절대 커밋하지 마세요.
- `history.json`은 로컬 채점 기록 파일입니다.
