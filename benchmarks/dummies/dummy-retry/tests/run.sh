#!/usr/bin/env bash
set -euo pipefail

OUTPUT="${CAE_ARTIFACT_ROOT}/output.txt"
COUNTER_FILE="$(dirname "$CAE_ARTIFACT_ROOT")/test/attempt-counter"

if [[ ! -f "$COUNTER_FILE" ]]; then
    echo 1 > "$COUNTER_FILE"
else
    COUNT=$(cat "$COUNTER_FILE")
    echo $((COUNT + 1)) > "$COUNTER_FILE"
fi

COUNT=$(cat "$COUNTER_FILE")

# First attempt: fail with helpful feedback
if [[ "$COUNT" -eq 1 ]]; then
    echo "FAIL: I need a specific greeting in a specific file."
    echo "Hint: create output.txt containing exactly 'hello world' (no quotes)."
    exit 1
fi

# Second+ attempt: check for correct content
if [[ ! -f "$OUTPUT" ]]; then
    echo "FAIL: output.txt not found"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python || echo "")
"$PYTHON" -c "
import sys
content = open('$OUTPUT').read().strip().lower()
if content == 'hello world':
    print('PASS')
    sys.exit(0)
else:
    print(f'FAIL: expected \"hello world\", got \"{content}\"')
    sys.exit(1)
"
