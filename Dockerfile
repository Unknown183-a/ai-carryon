# AI CarryON — Cloud Run image
# Same image is used for both the dashboard (Cloud Run service) and the
# scheduler (Cloud Run Job) — only the container command differs, set at
# deploy time. See DEPLOY.md for both commands.

FROM python:3.11-slim

# ffmpeg is required by moviepy/imageio-ffmpeg for video rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects PORT — Streamlit must listen on it and on 0.0.0.0
ENV PORT=8080
EXPOSE 8080

# Default command runs the dashboard. The Cloud Run Job for the scheduler
# overrides this at deploy time (see DEPLOY.md), so no separate image needed.
CMD streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
