# CAE container images
#
# Build:
#   podman build --target cae-worker-base -t cae-worker-base .
#   podman build --target cae-tester-base -t cae-tester-base .
#   podman build --target cae-worker-fat  -t cae-worker-fat  .
#   podman build --target cae-worker-pi   -t cae-worker-pi   .
#
# Or use scripts/build-images.sh

ARG PYTHON_VERSION=3.11
ARG DEBIAN_VERSION=bookworm

# ---------------------------------------------------------------------------
# Base — minimal but "feels real"
# ---------------------------------------------------------------------------
# Python is required because the CAE worker/tester run as Python modules.
# Everything else here is generic tooling that would be unreasonable to
# withhold from an agent: a compiler for native deps, git for cloning,
# curl/ca-certificates for HTTPS, bash for scripts.
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION} AS cae-base

RUN sed -i 's|http://deb.debian.org/debian|http://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's|http://deb.debian.org/debian-security|http://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /cae

# ---------------------------------------------------------------------------
# Fat base — common language runtimes so agent tool choice is less biased
# ---------------------------------------------------------------------------
# Adds Go, Rust, Java (OpenJDK), and Node.js to cae-base.  Python is already
# present.  C# and other niche runtimes are intentionally omitted because
# they are non-trivial to set up in Debian slim.
FROM cae-base AS cae-fat

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        golang-go \
        openjdk-17-jdk-headless \
        rustc cargo \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Worker / Tester (minimal)
# ---------------------------------------------------------------------------
FROM cae-base AS cae-worker-base
LABEL role=worker
ENTRYPOINT ["python", "-m", "cae.worker"]

FROM cae-base AS cae-tester-base
LABEL role=tester
ENTRYPOINT ["python", "-m", "cae.tester"]

# ---------------------------------------------------------------------------
# Worker / Tester (fat)
# ---------------------------------------------------------------------------
FROM cae-fat AS cae-worker-fat
LABEL role=worker
ENTRYPOINT ["python", "-m", "cae.worker"]

FROM cae-fat AS cae-tester-fat
LABEL role=tester
ENTRYPOINT ["python", "-m", "cae.tester"]

# ---------------------------------------------------------------------------
# Standalone (bake framework in — no bind-mount needed for src/)
# ---------------------------------------------------------------------------
FROM cae-worker-base AS cae-worker-standalone
COPY src/ /cae/src/
ENV PYTHONPATH=/cae/src

FROM cae-tester-base AS cae-tester-standalone
COPY src/ /cae/src/
ENV PYTHONPATH=/cae/src

# ---------------------------------------------------------------------------
# Layered pi worker (Node.js + pi pre-installed)
# ---------------------------------------------------------------------------
# Based on the fat image so the pi agent can solve tasks in Go, Rust, Java,
# Python, or JS/TS without needing extra layers.
FROM cae-worker-fat AS cae-worker-pi
RUN npm install -g @earendil-works/pi-coding-agent
# `pi` is now in PATH

# ---------------------------------------------------------------------------
# Usage notes
# ---------------------------------------------------------------------------
# Development (bind-mount CAE source):
#   podman run --rm --userns=keep-id \
#     -v /host/run:/run:Z -v /host/src:/cae/src:Z -e PYTHONPATH=/cae/src \
#     cae-worker-base --volume /run --agent-mode echo
#
# Production (standalone image):
#   podman run --rm --userns=keep-id -v /host/run:/run:Z \
#     cae-worker-standalone --volume /run --agent-mode echo
#
# Fat worker for language-agnostic benchmarks:
#   podman run --rm --userns=keep-id \
#     -v /host/run:/run:Z -v /host/src:/cae/src:Z -e PYTHONPATH=/cae/src \
#     cae-worker-fat --volume /run --agent-mode echo
#
# --userns=keep-id  → rootless UID mapping (host user = container root)
# -d is NOT used     → host process mirrors subprocess.Popen semantics
# :Z on volumes      → SELinux label relabeling
# --net=none         → tester only (no network during evaluation)
#
# For full docs see docs/container-mode.md
# vim: set ft=dockerfile :
