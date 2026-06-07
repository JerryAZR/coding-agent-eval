#!/usr/bin/env bash
set -euo pipefail

OUTPUT="${CAE_ARTIFACT_ROOT}/output.txt"
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
