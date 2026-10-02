# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Microsoft ODBC Driver 18 voor Azure SQL Database (uitschakelen met --build-arg INSTALL_MSSQL_DRIVER=false)
ARG INSTALL_MSSQL_DRIVER=true

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN if [ "$INSTALL_MSSQL_DRIVER" = "true" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends curl ca-certificates libgssapi-krb5-2 \
        && . /etc/os-release \
        && curl -sSL -o /tmp/packages-microsoft-prod.deb \
           "https://packages.microsoft.com/config/debian/${VERSION_ID%%.*}/packages-microsoft-prod.deb" \
        && dpkg -i /tmp/packages-microsoft-prod.deb \
        && rm /tmp/packages-microsoft-prod.deb \
        && apt-get update \
        && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
        && apt-get purge -y curl \
        && apt-get autoremove -y \
        && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app

COPY requirements.txt requirements-ai.txt requirements-azure-sql.txt ./
RUN pip install -r requirements.txt -r requirements-ai.txt \
    && if [ "$INSTALL_MSSQL_DRIVER" = "true" ]; then pip install -r requirements-azure-sql.txt; fi

COPY pyproject.toml README.md alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN pip install --no-deps . \
    && useradd --create-home --uid 10001 app

USER app

ENV APP_ENV=production \
    PORT=8000 \
    RUN_MIGRATIONS=true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/v1/health', timeout=4)"

# Migraties draaien bij het opstarten; --proxy-headers zorgt voor https-URL's achter de ingress.
CMD ["sh", "-c", "if [ \"$RUN_MIGRATIONS\" = \"true\" ]; then alembic upgrade head; fi && exec uvicorn --factory ledenadmin.main:create_app --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips='*'"]
