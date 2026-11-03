#!/bin/sh
set -e

# config.py isn't in the image; docker/compose.yml mounts it. Without this
# check the first sign would be an ImportError from deep in the app.
config=${VC_CONFIG_FILE:-/app/config.py}
if [ ! -f "$config" ]; then
    echo "There's no $config: mount one (see docker/compose.yml)." >&2
    exit 1
fi

# Once, before gunicorn starts its workers: build a new database from the
# models, or bring an existing one up to date with its migrations.
flask setup-db

exec "$@"
