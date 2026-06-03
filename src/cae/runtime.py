"""Runtime abstraction for spawning worker and tester processes.

Provides a unified interface over local subprocesses and rootless containers.
When container mode is implemented, ``ContainerRuntime`` will use Podman
without changing any manager code.
"""
from __future__ import annotations

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


class ContainerRuntime(Runtime):
    """Rootless Podman container runtime (stubbed)."""

    def spawn_worker(
        self,
        volume: Volume,
        agent_cmd: list[str] | None = None,
        agent_mode: str = "pi",
    ) -> subprocess.Popen:
        raise NotImplementedError(
            "ContainerRuntime.spawn_worker is not yet implemented. "
            "Use mode='local' for local subprocess execution."
        )

    def spawn_tester(self, volume: Volume, benchmark: Benchmark, phase_id: str) -> subprocess.CompletedProcess:
        raise NotImplementedError(
            "ContainerRuntime.spawn_tester is not yet implemented. "
            "Use mode='local' for local subprocess execution."
        )


def runtime_for_mode(mode: str) -> Runtime:
    """Return a ``Runtime`` instance for the given mode string."""
    if mode == "local":
        return LocalRuntime()
    if mode == "container":
        return ContainerRuntime()
    raise ValueError(f"Unknown runtime mode: {mode!r}. Expected 'local' or 'container'.")
