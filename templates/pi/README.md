# Pi Agent Template

Template directory for running the [pi coding agent](https://pi.dev) inside CAE.

## Files

| File | Purpose |
|------|---------|
| `.cae-startup.sh` | Installs `pi` via `curl` if not present. Runs once per worker spawn. |
| `.cae-env` | Environment variables injected into the worker process. |
| `agent/` | Python package auto-imported by the worker. Add custom `@register_client` adapters here. |

## Usage

```bash
# Local mode (pi must be on host PATH or installed by startup script)
PYTHONPATH=src python -m cae run \
  --mode local \
  --suite benchmarks/dummy-suite/suite.json \
  --agent-mode pi \
  --agent-template templates/pi

# Container mode (pi installed by startup script or baked into image)
PYTHONPATH=src python -m cae run \
  --mode container \
  --suite benchmarks/dummy-suite/suite.json \
  --agent-mode pi \
  --agent-template templates/pi

# Container mode with pi baked into image (faster cold start)
podman build --target cae-worker-pi -t cae-worker-pi .
PYTHONPATH=src python -m cae run \
  --mode container \
  --suite benchmarks/dummy-suite/suite.json \
  --agent-mode pi \
  --worker-image cae-worker-pi \
  --agent-template templates/pi
```

## Baking pi into an Image Layer

Installing pi on every worker spawn adds ~10-30s per benchmark.  For faster
runs, extend the base image:

```dockerfile
FROM cae-worker-base
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://pi.dev/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*
```

The `cae-worker-pi` target in `images/Dockerfile` already does this via npm.
See `docs/container-mode.md` for details.
