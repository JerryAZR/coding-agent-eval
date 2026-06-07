#!/usr/bin/env bash
set -euo pipefail

ARTIFACT="${CAE_ARTIFACT_ROOT:-.}/cinterp"
PHASE="${CAE_PHASE:-phase-1}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -x "$ARTIFACT" ]]; then
    echo "FAIL: cinterp not found or not executable at $ARTIFACT"
    exit 1
fi

case "$PHASE" in
    phase-1) META_FILES=("$SCRIPT_DIR/phase-1.json") ;;
    phase-2) META_FILES=("$SCRIPT_DIR/phase-1.json" "$SCRIPT_DIR/phase-2.json") ;;
    phase-3) META_FILES=("$SCRIPT_DIR/phase-1.json" "$SCRIPT_DIR/phase-2.json" "$SCRIPT_DIR/phase-3.json") ;;
    *)
        echo "FAIL: unknown phase: $PHASE"
        exit 1
        ;;
esac

python3 - "$ARTIFACT" "$SCRIPT_DIR" "${META_FILES[@]}" <<'PY'
import json, subprocess, sys

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

        result = subprocess.run(
            ["timeout", "5s", ARTIFACT, source_file],
            capture_output=True,
            text=True,
        )
        got_exit = result.returncode
        got_stdout = result.stdout
        got_stderr = result.stderr

        # Timeout
        if got_exit == 124:
            print(f"FAIL {name}: timed out after 5s")
            failed += 1
            continue

        # Exit code check
        if got_exit != want_exit:
            print(f"FAIL {name}: expected exit {want_exit}, got {got_exit}")
            failed += 1
            continue

        # Positive test: check stdout
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
            # Error test: check stderr non-empty
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
