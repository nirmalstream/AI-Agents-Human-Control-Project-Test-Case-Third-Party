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
# Chromium sometimes needs more than browser-use's 30 s to start under Docker Desktop (seen on Windows).
ENV TIMEOUT_BrowserStartEvent=120 TIMEOUT_BrowserLaunchEvent=120 TIMEOUT_BrowserConnectedEvent=120
CMD ["python", "run_case.py"]
