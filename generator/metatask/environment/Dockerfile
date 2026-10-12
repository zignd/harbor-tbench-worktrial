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

# Toolchains, installed with the same lines as recipes/*.dockerfile so this container
# matches a task image that pastes a recipe. Testing aid only: task images install
# their own toolchain from the recipe (generated tasks stay self-contained).
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain 1.82.0
ENV PATH="/root/.cargo/bin:${PATH}"
RUN curl -fsSL "https://go.dev/dl/go1.22.5.linux-$(dpkg --print-architecture).tar.gz" | tar -C /usr/local -xz
ENV PATH="/usr/local/go/bin:${PATH}"
RUN curl -fsSL "https://nodejs.org/dist/v20.17.0/node-v20.17.0-linux-$(dpkg --print-architecture | sed s/amd64/x64/).tar.gz" | tar -C /usr/local --strip-components=1 -xz
COPY recipes /app/recipes

WORKDIR /app
# Pipeline-owned files, pre-placed: the author writes everything else.
COPY standard_test.sh /app/output/tests/test.sh
COPY task.toml /app/output/task.toml
