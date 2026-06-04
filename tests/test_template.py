"""Tests for agent template setup utilities."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cae.template import apply_template, _merge_env


class TestApplyTemplate(unittest.TestCase):
    def test_copies_all_files_recursively(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            (template_dir / "main.py").write_text("main")
            nested = template_dir / "lib"
            nested.mkdir()
            (nested / "util.py").write_text("util")

            apply_template(impl_dir, template_dir)

            self.assertTrue((impl_dir / "main.py").exists())
            self.assertEqual((impl_dir / "main.py").read_text(), "main")
            self.assertTrue((impl_dir / "lib" / "util.py").exists())
            self.assertEqual((impl_dir / "lib" / "util.py").read_text(), "util")

    def test_copies_dotfiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            pi_dir = template_dir / ".pi"
            pi_dir.mkdir()
            (pi_dir / "config.json").write_text("{}")

            claude_dir = template_dir / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text("[]")

            apply_template(impl_dir, template_dir)

            self.assertEqual((impl_dir / ".pi" / "config.json").read_text(), "{}")
            self.assertEqual(
                (impl_dir / ".claude" / "settings.json").read_text(), "[]"
            )

    def test_overwrites_existing_files_on_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            (impl_dir / "main.py").write_text("old")
            (template_dir / "main.py").write_text("new")

            apply_template(impl_dir, template_dir)

            self.assertEqual((impl_dir / "main.py").read_text(), "new")

    def test_preserves_existing_files_when_no_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            existing_dir = impl_dir / "data"
            existing_dir.mkdir()
            (existing_dir / "old.txt").write_text("old")

            template_data = template_dir / "data"
            template_data.mkdir()
            (template_data / "new.txt").write_text("new")

            apply_template(impl_dir, template_dir)

            self.assertEqual((impl_dir / "data" / "old.txt").read_text(), "old")
            self.assertEqual((impl_dir / "data" / "new.txt").read_text(), "new")

    def test_raises_when_template_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            missing_template = Path(tmp) / "does_not_exist"
            impl_dir.mkdir()

            with self.assertRaises(FileNotFoundError):
                apply_template(impl_dir, missing_template)

    def test_works_when_template_dir_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            info = apply_template(impl_dir, template_dir)

            self.assertEqual(info.env, {})
            self.assertIsNone(info.venv_python)
            self.assertIsNone(info.agent_path)
            self.assertIsNone(info.startup_script)


class TestTemplateInfoFields(unittest.TestCase):
    def test_env_populated_from_cae_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            (template_dir / ".cae-env").write_text(
                "FOO=bar\nBAZ = qux\nIGNORE_ME\n"
            )

            info = apply_template(impl_dir, template_dir)

            self.assertEqual(info.env, {"FOO": "bar", "BAZ": "qux"})

    def test_env_skips_comments_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            (template_dir / ".cae-env").write_text(
                "\n# comment\n\nKEY=value\n# another comment\n\n"
            )

            info = apply_template(impl_dir, template_dir)

            self.assertEqual(info.env, {"KEY": "value"})

    def test_env_empty_when_cae_env_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            info = apply_template(impl_dir, template_dir)

            self.assertEqual(info.env, {})

    def test_venv_python_when_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            venv_python = template_dir / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True)
            venv_python.write_text("#!/bin/sh")

            info = apply_template(impl_dir, template_dir)

            self.assertIsInstance(info.venv_python, Path)
            self.assertEqual(info.venv_python, impl_dir / ".venv" / "bin" / "python")

    def test_venv_python_none_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            info = apply_template(impl_dir, template_dir)

            self.assertIsNone(info.venv_python)

    def test_agent_path_when_directory_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            (template_dir / "agent").mkdir()
            (template_dir / "agent" / "__init__.py").write_text("")

            info = apply_template(impl_dir, template_dir)

            self.assertIsInstance(info.agent_path, Path)
            self.assertEqual(info.agent_path, impl_dir / "agent")

    def test_agent_path_none_when_directory_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            info = apply_template(impl_dir, template_dir)

            self.assertIsNone(info.agent_path)

    def test_startup_script_when_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            (template_dir / ".cae-startup.sh").write_text("#!/bin/sh\necho ok\n")

            info = apply_template(impl_dir, template_dir)

            self.assertIsInstance(info.startup_script, Path)
            self.assertEqual(info.startup_script, impl_dir / ".cae-startup.sh")

    def test_startup_script_none_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            impl_dir = Path(tmp) / "impl"
            template_dir = Path(tmp) / "template"
            impl_dir.mkdir()
            template_dir.mkdir()

            info = apply_template(impl_dir, template_dir)

            self.assertIsNone(info.startup_script)


class TestMergeEnv(unittest.TestCase):
    def test_merges_base_and_overrides(self):
        base = {"A": "1", "B": "2"}
        overrides = {"B": "3", "C": "4"}

        result = _merge_env(base, overrides, None, None)

        self.assertEqual(result, {"A": "1", "B": "3", "C": "4"})

    def test_overrides_take_precedence(self):
        base = {"KEY": "base"}
        overrides = {"KEY": "override"}

        result = _merge_env(base, overrides, None, None)

        self.assertEqual(result["KEY"], "override")

    def test_prepend_pythonpath_when_existing(self):
        base = {"PYTHONPATH": "/existing"}

        result = _merge_env(base, {}, "/prepend", None)

        self.assertEqual(result["PYTHONPATH"], "/prepend:/existing")

    def test_prepend_pythonpath_when_missing(self):
        result = _merge_env({}, {}, "/prepend", None)

        self.assertEqual(result["PYTHONPATH"], "/prepend")

    def test_prepend_path_when_existing(self):
        base = {"PATH": "/usr/bin"}

        result = _merge_env(base, {}, None, "/opt/bin")

        self.assertEqual(result["PATH"], "/opt/bin:/usr/bin")

    def test_prepend_path_when_missing(self):
        result = _merge_env({}, {}, None, "/opt/bin")

        self.assertEqual(result["PATH"], "/opt/bin")

    def test_prepend_both_simultaneously(self):
        base = {"PYTHONPATH": "/py", "PATH": "/bin"}

        result = _merge_env(base, {}, "/py2", "/bin2")

        self.assertEqual(result["PYTHONPATH"], "/py2:/py")
        self.assertEqual(result["PATH"], "/bin2:/bin")


if __name__ == "__main__":
    unittest.main()
