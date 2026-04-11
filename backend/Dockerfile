FROM python:3.12-slim

# 시스템 라이브러리 설치 (PDF/HWP 파싱 필수)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm curl \
    poppler-utils \
    libpoppler-cpp-dev \
    fonts-nanum fonts-nanum-coding \
    && npm install -g kordoc pdfjs-dist || true \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

# 앱 복사
COPY . /app

# 서버 시작
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
