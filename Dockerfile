FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin adapt \
    && mkdir -p /data/.adapt \
    && chown -R adapt:adapt /data

USER adapt

EXPOSE 8000

CMD ["adapt", "serve", "/data", "--host", "0.0.0.0", "--port", "8000"]