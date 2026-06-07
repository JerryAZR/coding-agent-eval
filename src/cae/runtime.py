"""Runtime abstraction for spawning worker and tester processes.

Provides a unified interface over local subprocesses and rootless containers.
"""
from __future__ import annotations

import os
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Any
from pathlib import Path

from .benchmark import Benchmark
from .protocol import Volume
from .template import _merge_env


class Runtime(ABC):
    """Abstract interface for spawning worker and tester processes."""

    @abstractmethod
    def spawn_worker(
        self,
        volume: Volume,
        agent_cmd: list[str] | None = None,
    ) -> subprocess.Popen:
        """Start the worker process.

        Returns a ``subprocess.Popen``-like object with at least:
        ``poll()``, ``terminate()``, ``kill()``, and ``wait()``.
        """
        ...

    @abstractmethod
    def spawn_tester(self, volume: Volume, benchmark: Benchmark, phase_id: str) -> subprocess.CompletedProcess:
        """Run the tester and block until it completes.

        The tester must write its result to ``volume.results / "latest.json"``.
        """
        ...


def _impl_dir(volume: Volume) -> Path:
    return volume.root / "impl"


def _worker_env(volume: Volume) -> dict[str, str]:
    """Build the worker subprocess environment from the template in *impl_dir*.

    Sets ``$HOME`` to the impl directory, loads ``.cae-env``, prepends
    ``.venv/bin`` to ``PATH`` if a venv exists, and prepends ``agent/`` to
    ``PYTHONPATH`` if an adapter package exists.
    """
    impl = _impl_dir(volume)
    env = dict(os.environ)
    env["HOME"] = str(impl)
    env["CAE_ARTIFACT_ROOT"] = str(impl)

    # Resolve relative PYTHONPATH entries so they remain valid after chdir.
    if "PYTHONPATH" in env:
        cwd = Path.cwd()
        env["PYTHONPATH"] = ":".join(
            str(cwd / p) if not Path(p).is_absolute() else p
            for p in env["PYTHONPATH"].split(":")
        )

    # Load .cae-env
    env_file = impl / ".cae-env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()

    # Detect venv
    venv_bin = impl / ".venv" / "bin"
    prepend_path = str(venv_bin) if venv_bin.exists() else None

    # Detect agent adapter
    agent_path = impl / "agent"
    prepend_pythonpath = str(agent_path) if agent_path.exists() and agent_path.is_dir() else None

    return _merge_env(env, {}, prepend_pythonpath=prepend_pythonpath, prepend_path=prepend_path)


def _worker_python(volume: Volume) -> str:
    """Return the Python interpreter to use for the worker.

    Prefers ``impl/.venv/bin/python`` when a venv is present, otherwise
    falls back to ``sys.executable``.
    """
    venv_python = _impl_dir(volume) / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def _spawn_worker(cmd: list[str], env: dict[str, str], volume: Volume) -> subprocess.Popen:
    """Spawn worker with stdout/stderr drained to log files.

    Prevents pipe deadlock when the agent is verbose, and preserves output
    for post-run debugging in ``.cae/worker.stdout`` and ``.cae/worker.stderr``.
    """
    log_dir = volume.root / ".cae"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_f = open(log_dir / "worker.stdout", "w")
    stderr_f = open(log_dir / "worker.stderr", "w")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=stdout_f,
            stderr=stderr_f,
            text=True,
            env=env,
        )
    except Exception:
        stdout_f.close()
        stderr_f.close()
        raise
    proc._cae_stdout = stdout_f  # type: ignore[attr-defined]
    proc._cae_stderr = stderr_f  # type: ignore[attr-defined]
    return proc

# ---------------------------------------------------------------------------
# Local
# ---------------------------------------------------------------------------

class LocalRuntime(Runtime):
    """Local subprocess-based runtime."""
    def spawn_worker(
        self,
        volume: Volume,
        agent_cmd: list[str] | None = None,
    ) -> subprocess.Popen:
        cmd = [
            _worker_python(volume), "-m", "cae.worker",
            "--volume", str(volume.root.absolute()),
        ]
        if agent_cmd:
            cmd += ["--agent-cmd", " ".join(agent_cmd)]
        return _spawn_worker(cmd, _worker_env(volume), volume)

    def spawn_tester(self, volume: Volume, benchmark: Benchmark, phase_id: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        # Resolve relative PYTHONPATH entries so they remain valid after chdir.
        if "PYTHONPATH" in env:
            cwd = Path.cwd()
            env["PYTHONPATH"] = ":".join(
                str(cwd / p) if not Path(p).is_absolute() else p
                for p in env["PYTHONPATH"].split(":")
            )
        return subprocess.run(
            [
                sys.executable, "-m", "cae.tester",
                "--volume", str(volume.root.absolute()),
                "--task", str((benchmark.base_dir / "task.json").absolute()),
                "--phase", phase_id,
            ],
            capture_output=True,
            text=True,
            cwd=str(benchmark.tests_script.parent.absolute()),
            env=env,
        )


# ---------------------------------------------------------------------------
# Container (rootless Podman)
# ---------------------------------------------------------------------------

class ContainerRuntime(Runtime):
    """Rootless Podman container runtime.

    Spawns worker and tester processes as Podman containers.

    Parameters
    ----------
    engine:
        Container engine command (default: ``podman``).
    worker_image:
        Image for the worker container (default: ``cae-worker-base``).
    tester_image:
        Image for the tester container (default: ``cae-tester-base``).
    agent_mounts:
        Extra ``(host_path, container_path)`` bind-mounts to inject agent
        binaries or other dependencies into the worker container.
    src_dir:
        Directory containing the CAE framework source.  Mounted at
        ``/cae/src`` inside containers with ``PYTHONPATH`` set.
        Defaults to the parent of this file (``src/``).
    """

    def __init__(
        self,
        engine: str = "podman",
        worker_image: str = "cae-worker-base",
        tester_image: str = "cae-tester-base",
        agent_mounts: list[tuple[str, str]] | None = None,
        src_dir: Path | None = None,
    ):
        self.engine = engine
        self.worker_image = worker_image
        self.tester_image = tester_image
        self.agent_mounts = agent_mounts or []
        if src_dir is None:
            # src/cae/runtime.py -> src/
            self.src_dir = Path(__file__).parent.parent.absolute()
        else:
            self.src_dir = src_dir.absolute()

    def _podman_run(self, image: str, *, net_none: bool = False) -> list[str]:
        """Return the common ``podman run`` prefix."""
        cmd = [self.engine, "run", "--rm", "--userns=keep-id"]
        if net_none:
            cmd.append("--net=none")
        return cmd

    def _mount(self, host: Path | str, container: str) -> str:
        return f"-v{host}:{container}:Z"
    def spawn_worker(
        self,
        volume: Volume,
        agent_cmd: list[str] | None = None,
    ) -> subprocess.Popen:
        run_dir = volume.root.absolute()
        impl_dir = run_dir / "impl"

        # Detect venv on host filesystem (template already copied)
        venv_python = impl_dir / ".venv" / "bin" / "python"
        python_cmd = str(venv_python) if venv_python.exists() else "python"
        pythonpath = "/cae/src"
        agent_path = impl_dir / "agent"
        if agent_path.exists() and agent_path.is_dir():
            pythonpath = f"/run/impl/agent:{pythonpath}"

        cmd = self._podman_run(self.worker_image)
        cmd.append(self._mount(run_dir, "/run"))
        cmd.append(self._mount(self.src_dir, "/cae/src"))

        for host_path, container_path in self.agent_mounts:
            cmd.append(self._mount(host_path, container_path))

        cmd.extend(["-e", f"HOME=/run/impl"])
        cmd.extend(["-e", f"PYTHONPATH={pythonpath}"])
        cmd.extend(["-e", "CAE_ARTIFACT_ROOT=/run/impl"])

        # Pass .cae-env if present
        env_file = impl_dir / ".cae-env"
        if env_file.exists():
            cmd.extend(["--env-file", str(env_file)])

        # Prepend venv/bin to PATH if venv exists
        if venv_python.exists():
            cmd.extend(["-e", "PATH=/run/impl/.venv/bin:/usr/local/bin:/usr/bin:/bin"])

        cmd.extend([
            "--entrypoint", "",
            "-w", "/run/impl",
            self.worker_image,
            python_cmd, "-m", "cae.worker",
            "--volume", "/run",
        ])

        if agent_cmd:
            cmd += ["--agent-cmd", " ".join(agent_cmd)]

        return _spawn_worker(cmd, {}, volume)
    def spawn_tester(self, volume: Volume, benchmark: Benchmark, phase_id: str) -> subprocess.CompletedProcess:
        run_dir = volume.root.absolute()
        benchmark_dir = benchmark.base_dir.resolve()
        tests_script = benchmark.tests_script.resolve()
        tests_rel = tests_script.relative_to(benchmark_dir)
        tests_dir = f"/benchmark/{tests_rel.parent}"
        cmd = self._podman_run(self.tester_image, net_none=True)
        cmd.append(self._mount(run_dir, "/run"))
        cmd.append(self._mount(self.src_dir, "/cae/src"))
        cmd.append(self._mount(benchmark_dir, "/benchmark"))
        cmd.extend([
            "--entrypoint", "",
            "-e", "PYTHONPATH=/cae/src",
            "-e", f"CAE_PHASE={phase_id}",
            "-e", "CAE_ARTIFACT_ROOT=/run/impl",
            "-w", tests_dir,
            self.tester_image,
            "/usr/bin/python", "-m", "cae.tester",
            "--volume", "/run",
            "--task", "/benchmark/task.json",
            "--phase", phase_id,
        ])

        return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def runtime_for_mode(mode: str, **kwargs: Any) -> Runtime:
    """Return a ``Runtime`` instance for the given mode string.

    *mode="local"* returns ``LocalRuntime()``.
    *mode="container"* returns ``ContainerRuntime(**kwargs)``.
    """
    if mode == "local":
        return LocalRuntime()
    if mode == "container":
        return ContainerRuntime(**kwargs)
    raise ValueError(f"Unknown runtime mode: {mode!r}. Expected 'local' or 'container'.")
