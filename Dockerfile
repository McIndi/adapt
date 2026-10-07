# Official Python slim image at an exact patch tag. Pin the multi-platform
# index digest (not an amd64-only or arm64-only digest) so both publish
# architectures resolve the same input. Dependabot updates the tag and digest
# together. To refresh by hand, copy the index Digest from:
#   docker buildx imagetools inspect python:3.14.8-slim
FROM python:3.14.8-slim@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2

ARG IMAGE_VERSION="0.4.1"
ARG IMAGE_SOURCE="https://github.com/McIndi/adapt"
ARG IMAGE_REVISION="local"

LABEL org.opencontainers.image.title="Adapt Server" \
    org.opencontainers.image.description="Adaptive file-backed FastAPI server that turns datasets into CRUD APIs and UIs." \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.version="${IMAGE_VERSION}" \
    org.opencontainers.image.source="${IMAGE_SOURCE}" \
    org.opencontainers.image.revision="${IMAGE_REVISION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE requirements.runtime.lock ./

# Runtime dependencies only, at the exact hashed versions CI tests. See the
# header of requirements.runtime.lock for the command that generates it.
RUN pip install --no-cache-dir --require-hashes -r requirements.runtime.lock

COPY adapt ./adapt

RUN pip install --no-cache-dir --no-deps .

RUN groupadd --gid 1000 adapt \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin adapt \
    && mkdir -p /data/.adapt \
    && chown -R adapt:adapt /data

USER adapt

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

CMD ["adapt", "serve", "/data", "--host", "0.0.0.0", "--port", "8000"]
