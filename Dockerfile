# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Litestream maakt continu een back-up van de SQLite-database naar Azure Blob Storage
# (zie litestream.yml en docker-entrypoint.sh). Versie en checksums uit de GitHub-release.
ARG LITESTREAM_VERSION=0.5.17
ARG LITESTREAM_SHA256_AMD64=cfb371176d164437ae869f8351cfde49bd1804ae71c61923f75c9cba9c9c006d
ARG LITESTREAM_SHA256_ARM64=f8ca4a050095c1efbda2c4365172e61bf9d955ea0d9ac42f448b52e51819baa5
ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OS-beveiligingsupdates bovenop de basis-image (Trivy blokkeert HIGH/CRITICAL met beschikbare fix)
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN set -eu; \
    case "${TARGETARCH:-amd64}" in \
        amd64) asset=linux-x86_64; sum="$LITESTREAM_SHA256_AMD64" ;; \
        arm64) asset=linux-arm64; sum="$LITESTREAM_SHA256_ARM64" ;; \
        *) echo "Geen Litestream-build voor $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    url="https://github.com/benbjohnson/litestream/releases/download/v${LITESTREAM_VERSION}/litestream-${LITESTREAM_VERSION}-${asset}.tar.gz"; \
    python -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], '/tmp/litestream.tar.gz')" "$url"; \
    echo "$sum  /tmp/litestream.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/litestream.tar.gz -C /usr/local/bin litestream; \
    rm /tmp/litestream.tar.gz; \
    litestream version

WORKDIR /app

COPY requirements.txt requirements-ai.txt ./
RUN pip install -r requirements.txt -r requirements-ai.txt

COPY pyproject.toml README.md alembic.ini ./
COPY migrations ./migrations
COPY src ./src
COPY litestream.yml /etc/litestream.yml
COPY --chmod=755 docker-entrypoint.sh /app/docker-entrypoint.sh
# De database staat op de lokale schijf van de container (/data), niet op een netwerkshare:
# SQLite-vergrendeling werkt daar niet betrouwbaar. Litestream bewaart de back-up.
RUN pip install --no-deps . \
    && useradd --create-home --uid 10001 app \
    && mkdir /data \
    && chown app:app /data

USER app

ENV APP_ENV=production \
    PORT=8000 \
    RUN_MIGRATIONS=true \
    DATABASE_URL=sqlite:////data/ledenadmin.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/v1/health', timeout=4)"

# Migraties draaien bij het opstarten; --proxy-headers zorgt voor https-URL's achter de ingress.
CMD ["/app/docker-entrypoint.sh"]
