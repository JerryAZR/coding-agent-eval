#!/usr/bin/env bash
set -euo pipefail

ARTIFACT="${CAE_ARTIFACT_ROOT:-.}/pyc"
PHASE="${CAE_PHASE:-phase-1}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -x "$ARTIFACT" ]]; then
    echo "FAIL: pyc not found or not executable at $ARTIFACT"
    exit 1
fi

case "$PHASE" in
    phase-1) META_FILES=("$SCRIPT_DIR/phase-1.json") ;;
    *)
        echo "FAIL: unknown phase: $PHASE"
        exit 1
        ;;
esac

python3 - "$ARTIFACT" "$SCRIPT_DIR" "${META_FILES[@]}" <<'PY'
import json, os, subprocess, sys

ARTIFACT = sys.argv[1]
SCRIPT_DIR = sys.argv[2]
META_FILES = sys.argv[3:]

failed = 0
passed = 0

for meta_file in META_FILES:
    with open(meta_file) as f:
        data = json.load(f)

    for test in data["tests"]:
        name = test["name"]
        source_file = f"{SCRIPT_DIR}/{test['file']}"
        want_exit = test["exit"]
        want_stdout = test.get("stdout")
        is_error = test.get("error", False)

        os.chdir(SCRIPT_DIR)
        compile_result = subprocess.run(
            ["timeout", "30s", ARTIFACT, source_file],
            capture_output=True,
            text=True,
        )

        if compile_result.returncode == 124:
            print(f"FAIL {name}: compile timed out after 30s")
            failed += 1
            continue

        if compile_result.returncode != 0:
            print(f"FAIL {name}: compile failed with exit {compile_result.returncode}")
            if compile_result.stderr:
                print(compile_result.stderr)
            failed += 1
            continue

        run_result = subprocess.run(
            ["timeout", "5s", "./a.out"],
            capture_output=True,
            text=True,
        )
        got_exit = run_result.returncode
        got_stdout = run_result.stdout
        got_stderr = run_result.stderr

        if got_exit == 124:
            print(f"FAIL {name}: run timed out after 5s")
            failed += 1
            continue

        if got_exit != want_exit:
            print(f"FAIL {name}: expected exit {want_exit}, got {got_exit}")
            failed += 1
            continue

        if not is_error:
            if got_stdout != want_stdout:
                print(f"FAIL {name}: stdout mismatch")
                print("expected:")
                print(repr(want_stdout))
                print("got:")
                print(repr(got_stdout))
                failed += 1
                continue
        else:
            if not got_stderr.strip():
                print(f"FAIL {name}: expected error message on stderr")
                failed += 1
                continue

        print(f"PASS {name}")
        passed += 1

print(f"\nResults: {passed} passed, {failed} failed")
if failed > 0:
    sys.exit(1)
PY
