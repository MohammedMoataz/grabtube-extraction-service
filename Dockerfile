# GrabTube Extraction Service — single image bundling Python + yt-dlp + ffmpeg.
FROM python:3.12-slim

# ffmpeg is required for transcode/mux; yt-dlp is installed via pip (pinned in pyproject).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /tmp/grabtube && chown -R appuser /tmp/grabtube
USER appuser

ENV GT_PORT=8080 \
    GT_TMP_DIR=/tmp/grabtube
EXPOSE 8080

# HTTPS is terminated by an upstream reverse proxy; this serves plain HTTP behind it.
CMD ["sh", "-c", "uvicorn grabtube_extractor.main:app --host 0.0.0.0 --port ${GT_PORT}"]
