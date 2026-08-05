# ========== Backend Dockerfile ==========
FROM python:3.12-slim

WORKDIR /app

# 系统依赖（PyMuPDF 需要 libmupdf）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pyMuPDF==1.24.*

# 源码
COPY . .

# 暴露端口
EXPOSE 8000

# 开发模式启动（生产用 gunicorn + uvicorn workers）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
