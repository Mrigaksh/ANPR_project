# ── Stage: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

# System dependencies:
#   tesseract-ocr      → OCR engine (~22 MB, no torch needed)
#   tesseract-ocr-eng  → English language data
#   libglib2.0-0, libsm6, libxrender1, libxext6 → required by opencv-headless
#   libgomp1           → required by onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (best.onnx is included via COPY . .)
COPY . .

# Expose Flask port
EXPOSE 5000

# Run with gunicorn (production WSGI server)
# - 1 worker only → keeps memory safely under 512MB on Railway
#   (2 workers × ~250MB each = risk of OOM kill)
# - timeout 120s for slow ONNX inference on cold start
# - wsgi:app → uses wsgi.py which calls create_app()
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "wsgi:app"]