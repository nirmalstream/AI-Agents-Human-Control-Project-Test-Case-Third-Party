# The baseline agent: browser-use driving a headless Chromium (Debian package at /usr/bin/chromium).
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium fonts-liberation ca-certificates \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /agent
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1 \
    ANONYMIZED_TELEMETRY=false \
    BROWSER_USE_CLOUD_SYNC=false \
    BROWSER_USE_VERSION_CHECK=false \
    BROWSER_USE_SETUP_LOGGING=false
CMD ["python", "run_case.py"]
