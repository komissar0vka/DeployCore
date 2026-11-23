FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates msitools osslsigncode \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 deploycore \
    && install -d -m 0700 -o deploycore /var/lib/deploycore/packages
COPY deploycore ./deploycore
COPY alembic.ini .
COPY migrations ./migrations
USER 10001
CMD ["sh", "-c", "python -m deploycore.migrate && exec python -m uvicorn deploycore.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers"]
