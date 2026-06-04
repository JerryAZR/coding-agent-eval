"""Integration test for agent template wiring.

Runs a minimal benchmark with the probe template to verify that:
- Template files are copied into impl/
- .cae-env variables are visible to the agent
- .cae-startup.sh runs before the worker loop
- agent/ directory is added to PYTHONPATH
- $HOME points to the impl directory
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROBE_BENCH = Path(__file__).parent / "fixtures" / "probe-benchmark"
PROBE_TEMPLATE = Path(__file__).parent / "fixtures" / "probe-template"


class TestProbeTemplateContainer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name)
        self.volume_dir = self.run_dir / "volumes"
        self.volume_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skipUnless(shutil.which("podman"), "podman not available")
    def test_container_mode_with_probe_template(self):
        result = subprocess.run(
            [
                sys.executable, "-m", "cae",
                "run",
                "--suite", str(PROBE_BENCH / "suite.json"),
                "--volume", str(self.volume_dir),
                "--agent-mode", "probe",
                "--agent-template", str(PROBE_TEMPLATE),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
            env={**dict(subprocess.os.environ), "PYTHONPATH": str(Path(__file__).parent.parent / "src")},
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}\nstdout: {result.stdout}")

        run_dirs = list(self.volume_dir.iterdir())
        self.assertEqual(len(run_dirs), 1, f"Expected one run dir, got: {run_dirs}")
        bench_dir = run_dirs[0] / "probe-benchmark"
        output_file = bench_dir / "impl" / "output.txt"
        self.assertTrue(output_file.exists(), f"output.txt not found in {bench_dir / 'impl'}")

        data = json.loads(output_file.read_text())
        self.assertEqual(data["home"], "/run/impl")
        self.assertEqual(data["probe_var"], "from_template")
        self.assertTrue(data["startup_ran"])
        self.assertTrue(data["pythonpath_has_agent"])


if __name__ == "__main__":
    unittest.main()
