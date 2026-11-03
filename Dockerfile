# syntax=docker/dockerfile:1

# Turn Pipfile.lock into a requirements file for pip, so the lock is the only
# list of versions to keep up to date. Pipenv stays in this stage, out of the
# image.
FROM python:3.10-alpine AS requirements
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install pipenv
WORKDIR /lock
COPY ./Pipfile ./Pipfile.lock ./
RUN pipenv requirements > requirements.txt

FROM python:3.10-alpine

COPY --from=requirements /lock/requirements.txt /app/requirements.txt

# pymongo and sqlalchemy have no musllinux wheel, so they build from source;
# without a compiler pip quietly falls back to pure Python. Install, build and
# remove the build dependencies in one layer so they don't end up in the image.
# The cache mount keeps pip's downloads between builds.
RUN --mount=type=cache,id=vc-pip,target=/root/.cache/pip \
    apk add --no-cache --virtual .build-dependencies build-base \
    && python -m pip install --upgrade -r /app/requirements.txt \
    && apk del .build-dependencies

# config.py isn't copied in: it holds the live credentials, so mount it at
# /app/config.py when running the container.
WORKDIR /app
COPY ./app /app/app
COPY ./migrations /app/migrations
# For the one-off move from MongoDB (#4); remove it with the Mongo packages.
COPY ./scripts /app/scripts
ENV FLASK_APP=app

RUN adduser -D vc
USER vc

EXPOSE 19999
# The long timeout is for Sync and Sync Notes, which run inside the request and
# can take minutes; gunicorn's default 30 seconds would kill them partway
# through. Bring it back down when the sync moves out of the request (#11).
CMD [ "gunicorn", "-w", "2", "--timeout", "600", "--bind", "0.0.0.0:19999", "--access-logfile", "-", "app:app" ]
