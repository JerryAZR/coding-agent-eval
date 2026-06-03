#!/bin/bash
set -euo pipefail

ARTIFACT="${CAE_ARTIFACT_ROOT:-.}/nlm-eval"
PHASE="${CAE_PHASE:-phase-1}"

if [[ ! -x "$ARTIFACT" ]]; then
  echo "FAIL: nlm-eval binary not found or not executable at $ARTIFACT"
  exit 1
fi

run_test() {
  local name="$1"
  shift
  local expected="$1"
  shift
  local output
  output=$("$ARTIFACT" "$@" 2>/dev/null) || {
    echo "FAIL $name: non-zero exit for args: $*"
    return 1
  }
  if [[ "$output" != "$expected" ]]; then
    echo "FAIL $name: expected '$expected', got '$output'"
    return 1
  fi
  echo "PASS $name"
}

fail_test() {
  local name="$1"
  shift
  local output
  output=$("$ARTIFACT" "$@" 2>/dev/null) && {
    echo "FAIL $name: expected non-zero exit, got 0"
    return 1
  }
  echo "PASS $name"
}

case "$PHASE" in
  phase-1)
    run_test "int_plus"       "3"     1 plus 2
    run_test "int_minus"      "2"     5 minus 3
    run_test "decimal_plus"   "3"     1.5 plus 1.5
    run_test "decimal_minus"  "0.5"   2.0 minus 1.5
    run_test "negative_plus"  "-1"    -2 plus 1
    run_test "large"          "1000000" 500000 plus 500000
    fail_test "invalid_op"    1 times 2
    fail_test "missing_arg"   1 plus
    ;;

  phase-2)
    run_test "chain_two"      "9"     10 minus 3 plus 2
    run_test "chain_three"    "8"     10 minus 3 plus 2 minus 1
    run_test "chain_all_plus" "15"    1 plus 2 plus 3 plus 4 plus 5
    run_test "chain_mixed"    "0"     5 plus 5 minus 10
    run_test "chain_decimal"  "2.5"   1.5 plus 2.0 minus 1.0
    run_test "chain_negative" "-5"    -1 minus 2 minus 2
    ;;

  phase-3)
    run_test "paren_simple"    "5"     10 minus '(' 3 plus 2 ')'
    run_test "paren_nested"    "3"     10 minus '(' 3 plus '(' 2 plus 2 ')' ')'
    run_test "paren_chain"     "12"    10 plus '(' 3 minus 2 ')' plus 1
    run_test "paren_negative"  "-6"    '(' -1 minus 2 ')' minus 3
    ;;

  *)
    echo "FAIL: unknown phase: $PHASE"
    exit 1
    ;;
esac

echo "All $PHASE tests passed"
