#!/usr/bin/env bash
set -e

# Read expected results from agent's echoed prompt
RESULTS_FILE="$CAE_ARTIFACT_ROOT/output.txt"
if [ ! -f "$RESULTS_FILE" ]; then
    echo "FAIL: output.txt not found"
    exit 1
fi

RESULTS=$(cat "$RESULTS_FILE")
IFS=',' read -ra EXPECTED <<< "$RESULTS"

# Track attempt count
COUNTER_FILE="$(dirname "$CAE_ARTIFACT_ROOT")/test/attempt-counter"
if [ ! -f "$COUNTER_FILE" ]; then
    echo 1 > "$COUNTER_FILE"
else
    COUNT=$(cat "$COUNTER_FILE")
    echo $((COUNT + 1)) > "$COUNTER_FILE"
fi

COUNT=$(cat "$COUNTER_FILE")

if [ "$COUNT" -gt "${#EXPECTED[@]}" ]; then
    echo "FAIL: attempt $COUNT exceeds expected results (${#EXPECTED[@]})"
    exit 1
fi

IDX=$((COUNT - 1))
RESULT="${EXPECTED[$IDX]}"

if [ "$RESULT" == "pass" ]; then
    echo "PASS"
    exit 0
else
    echo "FAIL: attempt $COUNT expected to fail"
    exit 1
fi
