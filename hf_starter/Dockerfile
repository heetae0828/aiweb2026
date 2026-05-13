# Walrus Study: OpenAI 기반 문제 생성 + 답안 채점 Gradio 앱
# HuggingFace Space 또는 Docker 배포를 위한 Dockerfile

FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libglib2.0-0 libsm6 libxrender1 libxext6 \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 7860

ENV SPACE_ID=docker-hf \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/').read()" || exit 1

CMD ["python", "app.py"]
