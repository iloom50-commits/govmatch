FROM python:3.12-slim

# Node.js 설치 (kordoc CLI용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm curl \
    && npm install -g kordoc pdfjs-dist \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# 앱 복사
COPY . /app

# 서버 시작
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
