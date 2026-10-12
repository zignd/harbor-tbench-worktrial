# Synthesis container for the authoring meta-task. Generated tasks must use the
# same base image, so the authoring agent can reproduce their setup here.
FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl git jq procps sqlite3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest==8.4.1

# uv, so the author can run the standard verifier (tests/test.sh) exactly as Harbor will.
RUN curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app
COPY reference /app/reference
# The verifier entry point is pipeline-owned; the author only writes test_outputs.py.
COPY standard_test.sh /app/output/tests/test.sh
