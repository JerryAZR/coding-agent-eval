#!/usr/bin/env bash
set -euo pipefail

OUTPUT="${CAE_ARTIFACT_ROOT}/output.txt"
if [[ ! -f "$OUTPUT" ]]; then
    echo "output.txt not found"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python || echo "")
"$PYTHON" -c "
import json, sys
with open('$OUTPUT') as f:
    data = json.load(f)
home = data.get('home')
assert home is not None, 'HOME not set'
assert data.get('probe_var') == 'from_template', 'CAE_PROBE_VAR mismatch: ' + str(data.get('probe_var'))
assert data.get('startup_ran') is True, 'startup script did not run'
assert data.get('pythonpath_has_agent') is True, 'agent path not in PYTHONPATH'
print('All assertions passed')
"
