# Synthesis container for the authoring meta-task. Generated tasks must use the
# same base image, so the authoring agent can reproduce their setup here.
FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl git jq procps sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest==8.4.1

WORKDIR /app
COPY reference /app/reference
RUN mkdir -p /app/output
