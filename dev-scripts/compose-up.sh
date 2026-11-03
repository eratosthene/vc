#!/bin/bash
# Start the dev compose setup: the app from this checkout's code, against its
# own MariaDB (on 127.0.0.1:3308).
#
#   dev-scripts/compose-up.sh [-d | --background]
#
# It runs in the foreground with the logs attached, so Ctrl-C stops it.
# -d starts it in the background instead, and says how to follow the logs
# and stop it. The app is on http://127.0.0.1:5560.
set -euo pipefail

cd "$(dirname "$0")/.."

compose_file=docker/compose.dev.yml
env_file=docker/.env
url=http://127.0.0.1:5560
background=false

usage() {
    sed -n '2,9s/^# \{0,1\}//p' "$0"
}

while [ $# -gt 0 ]; do
    case "$1" in
        -d | --background) background=true; shift ;;
        -h | --help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

# Compose reads docker/.env itself, and also takes the password from the
# environment, so only a missing one in both fails.
if [ -z "${VC_DEV_DB_PASSWORD:-}" ] &&
    ! grep -qs '^VC_DEV_DB_PASSWORD=.' "$env_file"; then
    echo "VC_DEV_DB_PASSWORD isn't set in $env_file. To make one:" >&2
    echo "  echo \"VC_DEV_DB_PASSWORD=\$(openssl rand -hex 16)\" >> $env_file" >&2
    exit 1
fi

if [ "$background" = false ]; then
    exec docker compose -f "$compose_file" up --build
fi

docker compose -f "$compose_file" up --build --detach
cat <<MSG

Started in the background; open $url once the app is up.
  Follow the logs: docker compose -f $compose_file logs -f
  Stop it:         docker compose -f $compose_file stop
MSG
