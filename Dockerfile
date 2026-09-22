FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /app/data && chown app:app /app/data && chmod 700 /app/data
COPY app.py catalog.py ./
COPY static ./static
USER app
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "3600", "--worker-tmp-dir", "/tmp", "--limit-request-field_size", "65536", "--access-logfile", "/dev/null", "app:app"]
