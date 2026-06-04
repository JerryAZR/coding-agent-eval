# Container Mode

Container mode runs the worker and tester in rootless Podman containers for full isolation. The manager stays unchanged — only the `Runtime` implementation differs.

## Quick Start

```bash
# 1. Build base images
./scripts/build-images.sh

# 2. Run with container mode
PYTHONPATH=src python -m cae run \
  --mode container \
  --suite benchmarks/nlm-eval/suite.json
```

## Architecture

```
Host                                Container
─────────────────────────────────────────────────────────
Manager ──spawn_worker()──▶  podman run cae-worker-base
                              ├─ volume/:/run:Z
                              ├─ src/:/cae/src:Z
                              └─ python -m cae.worker ...

Manager ──spawn_tester()──▶  podman run --net=none cae-tester-base
                              ├─ volume/:/run:Z
                              ├─ benchmark/:/benchmark:Z
                              ├─ src/:/cae/src:Z
                              └─ python -m cae.tester ...
```

| Feature | Worker | Tester |
|---------|--------|--------|
| `--rm` | Yes (auto-remove on exit) | Yes |
| `--userns=keep-id` | Yes (rootless UID map) | Yes |
| `--net=none` | No | Yes (no network during eval) |
| `-d` (detached) | No (mirrors `subprocess.Popen`) | No |
| `:Z` (SELinux) | Yes | Yes |

## Images

### Base Images

| Image | Purpose | Size |
|-------|---------|------|
| `cae-worker-base` | Runs agent, bind-mounts CAE source | ~60MB |
| `cae-tester-base` | Runs tests, bind-mounts CAE source | ~60MB |
| `cae-worker-standalone` | Worker with CAE baked in | ~65MB |
| `cae-tester-standalone` | Tester with CAE baked in | ~65MB |

### Layered Images (with agents)

| Image | Base | Adds |
|-------|------|------|
| `cae-worker-pi` | `cae-worker-base` | Node.js 20 + `pi` npm package |

Build a layered image:

```bash
podman build --target cae-worker-pi -t cae-worker-pi .
```

## Making Agents Available

The worker container needs your agent binary in PATH. Three options:

### Option A: Layer It (Recommended)

Create a Dockerfile that installs your agent:

```dockerfile
FROM cae-worker-base
RUN apt-get update && apt-get install -y nodejs npm \
    && npm install -g @earendil-works/pi-coding-agent
```

Build and use:

```bash
podman build -t cae-worker-pi -f Dockerfile.pi .
PYTHONPATH=src python -m cae run --mode container --worker-image cae-worker-pi ...
```

### Option B: Bind-Mount It

If your agent is a single binary or directory on the host:

```bash
PYTHONPATH=src python -m cae run \
  --mode container \
  --agent-mount /usr/local/bin/pi:/usr/local/bin/pi \
  --suite benchmarks/nlm-eval/suite.json
```

Repeat `--agent-mount` for multiple directories.

### Option C: Use Standalone Image

Bake the CAE framework into the image so no source bind-mount is needed:

```bash
./scripts/build-images.sh podman cae-worker-standalone cae-tester-standalone
podman run -v /host/run:/run:Z cae-worker-standalone --volume /run
```
## CLI Flags

Container mode adds these flags to `cae run`:

| Flag | Default | Description |
|------|---------|-------------|
| `--engine` | `podman` | Container engine (`podman` or `docker`) |
| `--worker-image` | `cae-worker-base` | Worker container image |
| `--tester-image` | `cae-tester-base` | Tester container image |
| `--agent-mount` | — | `HOST:CONTAINER` bind-mount (repeatable) |

- **Rootless**: Containers run as your host user via `--userns=keep-id`
- **No privilege**: No `--privileged`, no dangerous capabilities
- **Network isolation**: Tester has `--net=none`
- **Volume isolation**: Tester only sees `/run/impl` and `/benchmark/tests`
- **SELinux**: `:Z` flag relabels volumes for the container's security context

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `podman: command not found` | Podman not installed | `sudo apt-get install podman` |
| `permission denied` on volume | SELinux labels | Ensure `:Z` flag is present (runtime adds it automatically) |
| `command not found: pi` | Agent not in container PATH | Layer it or bind-mount it |
| `ModuleNotFoundError: cae` | PYTHONPATH wrong or src/ not mounted | Check `src_dir` mounts correctly |
| `Error: short-name did not resolve` | Image not found | Build it: `./scripts/build-images.sh` |
| Container exits immediately | Agent command invalid | Check `--agent-cmd` or image contents |
| Tests can't find fixtures | Benchmark mount wrong | Check benchmark directory mounted at `/benchmark` |

## Design Decisions

1. **No `-d` flag**: The host `podman` process mirrors `subprocess.Popen`. Terminating the host process terminates the container.
2. **Bind-mount CAE source by default**: Framework is actively changing; bind-mount avoids rebuilds during development.
3. **Generic base images**: No agent baked in. Users layer or bind-mount their agent.
4. **`--userns=keep-id`**: Rootless Podman maps host user to container root. Files created in container match host UID.
5. **`:Z` on all volumes**: Required for SELinux systems. Relabels volumes for the container's security context.

## Comparison: Local vs Container

| Aspect | Local | Container |
|--------|-------|-----------|
| Setup | None | Build images once |
| Isolation | Process-level | Filesystem + network |
| Security | Host user | Rootless, no network for tester |
| Performance | Fastest | Image pull + container startup |
| Reproducibility | Host-dependent | Fully reproducible |
| Agent availability | Host PATH | Must layer or bind-mount |

## Future Work

- [ ] Pre-built images on a registry
- [ ] Multi-arch builds (AMD64, ARM64)
- [ ] Cache layers for faster rebuilds
- [ ] Compose / Kubernetes orchestration for parallel suite execution
