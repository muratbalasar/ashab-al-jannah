# syntax=docker/dockerfile:1

# Litestream maakt continu een back-up van de SQLite-database naar Azure Blob Storage (zie
# litestream.yml en docker-entrypoint.sh). We bouwen de release-tag zelf: de officiële binary
# bevat Go-modules met bekende kwetsbaarheden (Trivy). Alleen die modules worden bijgewerkt;
# bij een nieuwe Litestream-release kan deze lijst kleiner worden of vervallen.
FROM --platform=$BUILDPLATFORM golang:1.26 AS litestream
ARG LITESTREAM_VERSION=0.5.17
ARG LITESTREAM_COMMIT=ccd326c175b583b5e82893a6078f06dcef5fba3f
ARG TARGETARCH
WORKDIR /src
RUN git clone --quiet --depth 1 --branch "v${LITESTREAM_VERSION}" \
        https://github.com/benbjohnson/litestream.git . \
    && test "$(git rev-parse HEAD)" = "$LITESTREAM_COMMIT"
RUN go get golang.org/x/crypto@v0.57.0 golang.org/x/net@v0.60.0 google.golang.org/grpc@v1.84.0 \
    && go mod tidy \
    && CGO_ENABLED=0 GOOS=linux GOARCH="${TARGETARCH:-amd64}" go build -trimpath \
        -ldflags "-s -w -X main.Version=${LITESTREAM_VERSION}" -o /out/litestream ./cmd/litestream

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OS-beveiligingsupdates bovenop de basis-image (Trivy blokkeert HIGH/CRITICAL met beschikbare fix)
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY --from=litestream /out/litestream /usr/local/bin/litestream
RUN litestream version

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
