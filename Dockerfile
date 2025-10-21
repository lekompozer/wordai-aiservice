FROM python:3.10-slim

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết và LibreOffice
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    pandoc \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt trước để tận dụng Docker cache
COPY requirements.txt .

# Cài đặt các thư viện Python chính trước
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Cài đặt google-genai và cerebras riêng để tránh anyio conflict
RUN pip install --no-cache-dir google-genai==1.29.0 --force-reinstall
RUN pip install --no-cache-dir cerebras-cloud-sdk==1.29.0

# Copy toàn bộ code
COPY . .

# Tạo thư mục logs và data nếu chưa có
RUN mkdir -p logs data

# Set biến môi trường
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production


# Expose port mà ứng dụng sẽ chạy
EXPOSE 8000

# Thêm health check để kiểm tra ứng dụng có chạy được không
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Khởi động ứng dụng với logging verbose hơn
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120", "--log-level", "info"]