#!/usr/bin/env bash
set -euo pipefail

OUTPUT="${CAE_ARTIFACT_ROOT}/output.txt"
PHASE2="${CAE_ARTIFACT_ROOT}/phase2.txt"
PHASE="${CAE_PHASE:-unknown}"

PYTHON=$(command -v python3 || command -v python || echo "")
"$PYTHON" -c "
import sys
phase = '$PHASE'

if phase == 'phase-1':
    content = open('$OUTPUT').read().strip()
    if content == '7':
        print('PASS')
        sys.exit(0)
    else:
        print(f'FAIL: expected \"7\", got \"{content}\"')
        sys.exit(1)
elif phase == 'phase-2':
    if not open('$OUTPUT').read().strip() == '7':
        print('FAIL: output.txt was modified')
        sys.exit(1)
    content = open('$PHASE2').read().strip()
    if content == '21':
        print('PASS')
        sys.exit(0)
    else:
        print(f'FAIL: expected \"21\" in phase2.txt, got \"{content}\"')
        sys.exit(1)
else:
    print(f'FAIL: unknown phase {phase}')
    sys.exit(1)
"
