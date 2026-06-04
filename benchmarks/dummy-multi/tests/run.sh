#!/usr/bin/env bash
set -euo pipefail

OUTPUT="${CAE_ARTIFACT_ROOT}/output.txt"
PHASE="${CAE_PHASE:-unknown}"

if [[ ! -f "$OUTPUT" ]]; then
    echo "FAIL: output.txt not found"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python || echo "")
"$PYTHON" -c "
import sys
content = open('$OUTPUT').read().strip()
phase = '$PHASE'

if phase == 'phase-1':
    if content == '7':
        print('PASS')
        sys.exit(0)
    else:
        print(f'FAIL: expected \"7\", got \"{content}\"')
        sys.exit(1)
elif phase == 'phase-2':
    if content == '21':
        print('PASS')
        sys.exit(0)
    else:
        print(f'FAIL: expected \"21\", got \"{content}\"')
        sys.exit(1)
else:
    print(f'FAIL: unknown phase {phase}')
    sys.exit(1)
"
