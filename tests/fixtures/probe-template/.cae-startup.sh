#!/usr/bin/env bash
set -euo pipefail
PYTHON=$(command -v python3 || command -v python || echo "")
"$PYTHON" -c "import pathlib; pathlib.Path.home().joinpath('.startup-ran').touch()"
