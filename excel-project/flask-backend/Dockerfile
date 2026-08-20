FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GUNICORN_BIND=0.0.0.0:8000 \
    FORWARDED_ALLOW_IPS=*

WORKDIR /app

RUN groupadd --system excel && useradd --system --gid excel --home-dir /app excel

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/static/uploads \
    && chown -R excel:excel /app

USER excel
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--config=gunicorn.conf.py", "wsgi:app"]
