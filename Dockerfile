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
    ffmpeg \
    # Playwright/Chromium dependencies (comprehensive list)
    wget \
    ca-certificates \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-unifont \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libwayland-client0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxkbcommon0 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt trước để tận dụng Docker cache
COPY requirements.txt .

# Cài đặt các thư viện Python chính với cache mount
# BuildKit cache mount: pip cache được persist giữa các builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Cài đặt cerebras riêng để tránh anyio conflict
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install cerebras-cloud-sdk==1.29.0

# Install Playwright browsers (Chromium only, deps already installed above)
RUN playwright install chromium

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