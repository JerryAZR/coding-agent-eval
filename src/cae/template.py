"""Agent template setup utilities.

Handles copying template directories into the agent workspace, parsing
environment files, and detecting virtual environments.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TemplateInfo:
    """Result of applying a template to an impl directory."""

    env: dict[str, str]
    """Variables parsed from ``.cae-env``."""

    venv_python: Path | None
    """Absolute path to the venv python interpreter, or ``None``."""

    agent_path: Path | None
    """Absolute path to the ``agent/`` package directory, or ``None``."""

    startup_script: Path | None
    """Absolute path to ``.cae-startup.sh``, or ``None``."""


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a simple ``KEY=value`` env file.

    Lines starting with ``#`` and blank lines are skipped.
    No shell variable expansion or ``export`` keyword is supported.
    """
    env: dict[str, str] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def apply_template(impl_dir: Path, template_dir: Path) -> TemplateInfo:
    """Copy *template_dir* into *impl_dir* and inspect the result.

    The copy is recursive.  Dotfiles are copied normally.  Any existing
    files in *impl_dir* are left untouched unless they collide with a
    template file, in which case the template wins.
    """
    template_dir = template_dir.resolve()
    impl_dir = impl_dir.resolve()

    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    # Copy template contents into impl/
    for src in template_dir.iterdir():
        dst = impl_dir / src.name
        if src.is_dir():
            if dst.exists():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # Detect special files
    env_file = impl_dir / ".cae-env"
    env = _parse_env_file(env_file) if env_file.exists() else {}

    _venv_python = impl_dir / ".venv" / "bin" / "python"
    venv_python: Path | None = _venv_python if _venv_python.exists() else None

    _agent_path = impl_dir / "agent"
    agent_path: Path | None = _agent_path if _agent_path.exists() and _agent_path.is_dir() else None

    _startup_script = impl_dir / ".cae-startup.sh"
    startup_script: Path | None = _startup_script if _startup_script.exists() else None


    return TemplateInfo(
        env=env,
        venv_python=venv_python,
        agent_path=agent_path,
        startup_script=startup_script,
    )

def _merge_env(
    base: dict[str, str],
    overrides: dict[str, str],
    prepend_pythonpath: str | None,
    prepend_path: str | None,
) -> dict[str, str]:
    """Merge environment variables with optional PYTHONPATH / PATH prepending."""
    env = dict(base, **overrides)

    if prepend_pythonpath:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{prepend_pythonpath}:{existing}" if existing else prepend_pythonpath
        )

    if prepend_path:
        existing = env.get("PATH", "")
        env["PATH"] = (
            f"{prepend_path}:{existing}" if existing else prepend_path
        )

    return env
