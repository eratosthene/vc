# syntax=docker/dockerfile:1

# Turn Pipfile.lock into a requirements file for pip, so the lock is the only
# list of versions to keep up to date. Pipenv stays in this stage, out of the
# image.
FROM python:3.12-alpine AS requirements
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install pipenv
WORKDIR /lock
COPY ./Pipfile ./Pipfile.lock ./
RUN pipenv requirements > requirements.txt

FROM python:3.12-alpine

COPY --from=requirements /lock/requirements.txt /app/requirements.txt

# sqlalchemy has no musllinux wheel, so it builds from source;
# without a compiler pip quietly falls back to pure Python. Install, build and
# remove the build dependencies in one layer so they don't end up in the image.
# The cache mount keeps pip's downloads between builds.
RUN --mount=type=cache,id=vc-pip,target=/root/.cache/pip \
    apk add --no-cache --virtual .build-dependencies build-base \
    && python -m pip install --upgrade -r /app/requirements.txt \
    && apk del .build-dependencies

# config.py isn't copied in: it holds the live credentials, so the compose
# files mount it at /app/config.py, and a change to it needs no rebuild.
WORKDIR /app
COPY ./app /app/app
COPY ./migrations /app/migrations
# For the one-off move from MongoDB (#4); remove it with the Mongo packages.
COPY ./scripts /app/scripts
COPY --chmod=755 ./docker/docker-entrypoint.sh /app/docker-entrypoint.sh
ENV FLASK_APP=app

RUN adduser -D vc
USER vc

EXPOSE 19999
# The entrypoint checks config.py is mounted and runs `flask setup-db`, then
# starts the command below (or whatever the dev compose file runs instead).
ENTRYPOINT [ "/app/docker-entrypoint.sh" ]
# The sync runs in a background thread (app/syncjob.py), not in a request, so
# the 600 second timeout it needed (#14) is down to 120. That isn't gunicorn's
# default 30: the Print View for the whole collection still runs a query per
# artist in one request (#10). Once that's fixed, the flag can go.
CMD [ "gunicorn", "-w", "2", "--timeout", "120", "--bind", "0.0.0.0:19999", "--access-logfile", "-", "app:app" ]
