"""Runtime abstraction for spawning worker and tester processes.

Provides a unified interface over local subprocesses and rootless containers.
"""
from __future__ import annotations

import os
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path

from .benchmark import Benchmark
from .protocol import Volume


class Runtime(ABC):
    """Abstract interface for spawning worker and tester processes."""

    @abstractmethod
    def spawn_worker(
        self,
        volume: Volume,
        agent_cmd: list[str] | None = None,
        agent_mode: str = "pi",
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


# ---------------------------------------------------------------------------
# Local
# ---------------------------------------------------------------------------

class LocalRuntime(Runtime):
    """Local subprocess-based runtime."""

    def _env(self) -> dict[str, str]:
        env = dict(subprocess.os.environ)
        # Resolve relative PYTHONPATH entries so they remain valid after chdir.
        if "PYTHONPATH" in env:
            cwd = Path.cwd()
            env["PYTHONPATH"] = ":".join(
                str(cwd / p) if not Path(p).is_absolute() else p
                for p in env["PYTHONPATH"].split(":")
            )
        return env

    def spawn_worker(
        self,
        volume: Volume,
        agent_cmd: list[str] | None = None,
        agent_mode: str = "pi",
    ) -> subprocess.Popen:
        cmd = [
            sys.executable, "-m", "cae.worker",
            "--volume", str(volume.root.absolute()),
            "--agent-mode", agent_mode,
        ]
        if agent_cmd:
            cmd += ["--agent-cmd", " ".join(agent_cmd)]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self._env(),
        )

    def spawn_tester(self, volume: Volume, benchmark: Benchmark, phase_id: str) -> subprocess.CompletedProcess:
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
            env=self._env(),
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
        agent_mode: str = "pi",
    ) -> subprocess.Popen:
        run_dir = volume.root.absolute()

        cmd = self._podman_run(self.worker_image)
        cmd.append(self._mount(run_dir, "/run"))
        cmd.append(self._mount(self.src_dir, "/cae/src"))

        for host_path, container_path in self.agent_mounts:
            cmd.append(self._mount(host_path, container_path))

        cmd.extend([
            "-e", "PYTHONPATH=/cae/src",
            "-e", "CAE_ARTIFACT_ROOT=/run/impl",
            "-w", "/run/impl",
            self.worker_image,
            "/usr/bin/python", "-m", "cae.worker",
            "--volume", "/run",
            "--agent-mode", agent_mode,
        ])

        if agent_cmd:
            cmd += ["--agent-cmd", " ".join(agent_cmd)]

        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

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

def runtime_for_mode(mode: str, **kwargs) -> Runtime:
    """Return a ``Runtime`` instance for the given mode string.

    *mode="local"* returns ``LocalRuntime()``.
    *mode="container"* returns ``ContainerRuntime(**kwargs)``.
    """
    if mode == "local":
        return LocalRuntime()
    if mode == "container":
        return ContainerRuntime(**kwargs)
    raise ValueError(f"Unknown runtime mode: {mode!r}. Expected 'local' or 'container'.")
