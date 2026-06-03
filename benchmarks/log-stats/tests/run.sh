#!/bin/bash
set -euo pipefail

ARTIFACT="${CAE_ARTIFACT_ROOT:-.}/log-stats"
PHASE="${CAE_PHASE:-phase-1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -x "$ARTIFACT" ]]; then
  echo "FAIL: log-stats binary not found or not executable at $ARTIFACT"
  exit 1
fi
assert_json_eq() {
    local name="$1"
    local expected="$2"
    local actual="$3"
    python3 -c "
import json, sys
e = json.loads(sys.argv[1])
a = json.loads(sys.argv[2])
if e != a:
    print(f'FAIL {sys.argv[3]}: expected {e!r}, got {a!r}')
    sys.exit(1)
print(f'PASS {sys.argv[3]}')
" "$expected" "$actual" "$name"
}

case "$PHASE" in
  phase-1)
    output=$("$ARTIFACT" "$SCRIPT_DIR/fixtures/phase-1.log" 2>/dev/null)
    assert_json_eq "count_levels" '{"INFO":4,"DEBUG":2,"WARN":2,"ERROR":2}' "$output"
    ;;

  phase-2)
    output=$("$ARTIFACT" --level ERROR "$SCRIPT_DIR/fixtures/phase-2.log" 2>/dev/null)
    expected="2024-01-01 10:00:01 ERROR disk full
2024-01-01 10:00:03 ERROR disk full
2024-01-01 10:00:06 ERROR disk full"
    if [[ "$output" != "$expected" ]]; then
      echo "FAIL filter_error: output mismatch"
      echo "expected:"
      echo "$expected"
      echo "actual:"
      echo "$output"
      exit 1
    fi
    echo "PASS filter_error"

    # Invalid level should fail
    if "$ARTIFACT" --level FATAL "$SCRIPT_DIR/fixtures/phase-2.log" 2>/dev/null; then
      echo "FAIL invalid_level: expected non-zero exit"
      exit 1
    fi
    echo "PASS invalid_level"
    ;;

  phase-3)
    output=$("$ARTIFACT" --group-by hour "$SCRIPT_DIR/fixtures/phase-3.log" 2>/dev/null)
    assert_json_eq "hourly" '{"2024-01-01 00":2,"2024-01-01 01":3,"2024-01-01 02":1}' "$output"
    ;;

  *)
    echo "FAIL: unknown phase: $PHASE"
    exit 1
    ;;
esac

echo "All $PHASE tests passed"
