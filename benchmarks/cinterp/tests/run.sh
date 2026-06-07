#!/usr/bin/env bash
set -euo pipefail

ARTIFACT="${CAE_ARTIFACT_ROOT:-.}/cinterp"
PHASE="${CAE_PHASE:-phase-1}"

if [[ ! -x "$ARTIFACT" ]]; then
  echo "FAIL: cinterp not found or not executable at $ARTIFACT"
  exit 1
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# Each test is a C program.
# Expected stdout and exit code were pre-validated by compiling with gcc
# (plus a tiny print_int wrapper) during test design.

run_test() {
    local name="$1"
    local code="$2"
    local want_stdout="$3"
    local want_exit="$4"
    local file="$TMPDIR/${name}.c"

    printf '%s\n' "$code" > "$file"
    local got_stdout got_exit
    set +e
    got_stdout=$("$ARTIFACT" "$file" 2>/dev/null)
    got_exit=$?
    set -e

    if [[ "$got_exit" -ne "$want_exit" ]]; then
        echo "FAIL $name: expected exit $want_exit, got $got_exit"
        return 1
    fi
    if [[ "$got_stdout" != "$want_stdout" ]]; then
        echo "FAIL $name: stdout mismatch"
        echo "expected:"
        printf '%s\n' "$want_stdout" | cat -A
        echo "got:"
        printf '%s\n' "$got_stdout" | cat -A
        return 1
    fi
    echo "PASS $name"
}

run_error_test() {
    local name="$1"
    local code="$2"
    local file="$TMPDIR/${name}.c"

    printf '%s\n' "$code" > "$file"
    local got_stderr got_exit
    set +e
    got_stderr=$("$ARTIFACT" "$file" 2>&1 >/dev/null)
    got_exit=$?
    set -e

    if [[ "$got_exit" -eq 0 ]]; then
        echo "FAIL $name: expected non-zero exit, got 0"
        return 1
    fi
    if [[ -z "$got_stderr" ]]; then
        echo "FAIL $name: expected error message on stderr"
        return 1
    fi
    echo "PASS $name"
}

case "$PHASE" in
  phase-1)
    run_test "print_int" \
"int main() {
    print_int(42);
    return 0;
}" \
"42" \
0

    run_test "arithmetic" \
"int main() {
    print_int(1 + 2);
    print_int(10 - 3);
    print_int(4 * 5);
    print_int(20 / 4);
    print_int(17 % 5);
    return 0;
}" \
"3
7
20
5
2" \
0

    run_test "variables" \
"int main() {
    int x;
    x = 7;
    print_int(x);
    return 0;
}" \
"7" \
0

    run_test "assignment_chain" \
"int main() {
    int a;
    int b;
    a = b = 3;
    print_int(a);
    print_int(b);
    return 0;
}" \
"3
3" \
0

    run_test "if_true" \
"int main() {
    int x;
    x = 10;
    if (x > 5) {
        print_int(1);
    } else {
        print_int(0);
    }
    return 0;
}" \
"1" \
0

    run_test "if_false" \
"int main() {
    int x;
    x = 2;
    if (x > 5) {
        print_int(1);
    } else {
        print_int(0);
    }
    return 0;
}" \
"0" \
0

    run_test "while" \
"int main() {
    int i;
    i = 0;
    while (i < 3) {
        print_int(i);
        i = i + 1;
    }
    return 0;
}" \
"0
1
2" \
0

    run_test "comparisons" \
"int main() {
    print_int(1 == 1);
    print_int(1 != 2);
    print_int(1 < 2);
    print_int(2 > 1);
    print_int(1 <= 1);
    print_int(2 >= 2);
    return 0;
}" \
"1
1
1
1
1
1" \
0

    run_test "operator_precedence" \
"int main() {
    print_int(2 + 3 * 4);
    print_int(10 - 6 / 2);
    return 0;
}" \
"14
7" \
0

    run_test "return_code" \
"int main() {
    return 42;
}" \
"" \
42

    run_test "include_ignored" \
"#include <stdio.h>
int main() {
    print_int(99);
    return 0;
}" \
"99" \
0

    run_test "nested_control" \
"int main() {
    int i;
    i = 0;
    while (i < 2) {
        if (i == 0) {
            print_int(10);
        } else {
            print_int(20);
        }
        i = i + 1;
    }
    return 0;
}" \
"10
20" \
0

    run_error_test "div_zero" \
"int main() {
    int x;
    x = 1 / 0;
    print_int(x);
    return 0;
}"

    run_error_test "uninit" \
"int main() {
    int x;
    print_int(x);
    return 0;
}"
    ;;

  *)
    echo "FAIL: unknown phase: $PHASE"
    exit 1
    ;;
esac

echo "All $PHASE tests passed"
