#!/bin/sh
# Run the vc container on the live server. The image doesn't contain
# config.py, so it is mounted in. Temporary: delete this when the move to
# docker compose (#9) lands.
set -eu

# Replace the running container, if any, so this can be re-run after a rebuild.
sudo docker rm -f vc1 >/dev/null 2>&1 || true

sudo docker run -d --name vc1 --restart unless-stopped -p 19999:19999 \
  -v /volume1/docker/vc/config.py:/app/config.py:ro \
  vc:latest
