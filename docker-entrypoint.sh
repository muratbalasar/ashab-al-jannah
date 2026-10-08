#!/bin/sh
# Start de app in de container.
# Met LITESTREAM_REPLICA_URL zet Litestream eerst de database terug uit de back-up (als die
# lokaal nog niet bestaat) en repliceert daarna continu, met de app als subproces. Zonder die
# variabele start alleen de app. Er mag maar één container tegelijk draaien (maxReplicas=1).
set -eu

serve() {
    if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
        alembic upgrade head
    fi
    exec uvicorn --factory ledenadmin.main:create_app --host 0.0.0.0 --port "${PORT:-8000}" \
        --proxy-headers --forwarded-allow-ips='*'
}

if [ "${1:-}" = "serve" ] || [ -z "${LITESTREAM_REPLICA_URL:-}" ]; then
    serve
fi

case "${DATABASE_URL:-}" in
    sqlite:////*) db_path="/${DATABASE_URL#sqlite:////}" ;;
    sqlite+pysqlite:////*) db_path="/${DATABASE_URL#sqlite+pysqlite:////}" ;;
    *)
        echo "LITESTREAM_REPLICA_URL vereist een SQLite-DATABASE_URL met een absoluut pad," \
            "bijv. sqlite:////data/ledenadmin.db" >&2
        exit 1
        ;;
esac

export LITESTREAM_DB_PATH="$db_path"
export LITESTREAM_RETENTION="${LITESTREAM_RETENTION:-168h}"
mkdir -p "$(dirname "$db_path")"

# Lukt het terugzetten niet (bijv. geen toegang tot de opslag), dan stopt de container in plaats
# van met een lege database te starten en die als nieuwe back-up weg te schrijven.
litestream restore -config /etc/litestream.yml -if-db-not-exists -if-replica-exists "$db_path"
exec litestream replicate -config /etc/litestream.yml -exec "$0 serve"
