#!/bin/bash
# Run vc on this machine with Flask's reloading dev server, from the Pipenv
# environment (`pipenv install --dev`). For the app and a MariaDB in Docker,
# use compose-up.sh instead.
#
#   dev-scripts/run-local.sh [-H HOST] [-p PORT]
#
# It listens on 127.0.0.1:5561 unless told otherwise, by the options or by
# VC_HOST and VC_PORT. 5561 so it can run alongside compose-up.sh's app,
# which has 5560. It reads config.py, so point that at a database you can
# lose, such as compose-up.sh's MariaDB on 127.0.0.1:3308, and run
# `pipenv run flask --app app setup-db` once.
set -euo pipefail

cd "$(dirname "$0")/.."

host="${VC_HOST:-127.0.0.1}"
port="${VC_PORT:-5561}"

usage() {
    sed -n '2,12s/^# \{0,1\}//p' "$0"
}

while [ $# -gt 0 ]; do
    case "$1" in
        -H | --host) host="${2:?$1 needs a host}"; shift 2 ;;
        -p | --port) port="${2:?$1 needs a port}"; shift 2 ;;
        -h | --help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [ ! -f config.py ]; then
    echo "config.py is missing; copy config.py.tpl to config.py and fill it in." >&2
    exit 1
fi

if ! command -v pipenv >/dev/null 2>&1; then
    echo "pipenv is not installed; install it, then run \`pipenv install --dev\`." >&2
    exit 1
fi

exec pipenv run flask --app app run --debug --host "$host" --port "$port"
