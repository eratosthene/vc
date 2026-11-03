#!/bin/bash
# Build the image and start the app on the live server, from this checkout.
#
#   docker/live-up.sh [-n | --no-build]
#
# It runs `sudo docker compose -f docker/compose.yml build --pull`, then `up
# -d --force-recreate`, which replaces the running container. The container
# brings the database up to date itself as it starts. -n skips the build and
# starts the image already there, which is all a change to config.py needs.
set -euo pipefail

cd "$(dirname "$0")/.."

compose_file=docker/compose.yml
build=true

usage() {
    sed -n '2,9s/^# \{0,1\}//p' "$0"
}

while [ $# -gt 0 ]; do
    case "$1" in
        -n | --no-build) build=false; shift ;;
        -h | --help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

# The container mounts config.py rather than having it built in.
if [ ! -f config.py ]; then
    echo "config.py is missing; copy config.py.tpl to config.py and fill it in." >&2
    exit 1
fi

# --pull so an old cached base image doesn't get built on.
if [ "$build" = true ]; then
    sudo docker compose -f "$compose_file" build --pull
fi

# Recreated even when nothing in the compose file changed, since `up -d`
# alone doesn't notice an edit to the mounted config.py.
sudo docker compose -f "$compose_file" up -d --no-build --force-recreate
cat <<MSG

Started; the app is on port 19999 once it's up.
  Follow the logs: docker/live-logs.sh
  Stop it:         docker/live-down.sh
MSG
