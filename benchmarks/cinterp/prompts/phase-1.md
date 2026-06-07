# Build a C Interpreter

Your task is to build an interpreter for a restricted subset of C.

## Deliverable

A single executable named `cinterp` in the current directory.

## Interface

```
./cinterp <program.c>
```

The interpreter reads a C source file, executes it, and:
- Prints to stdout any output produced by `print_int()` calls
- Returns the value of `return` as the process exit code
- Prints a brief error message to stderr and exits with code 1 on runtime error

## Language Subset (Phase 1)

Your interpreter must support:

- **One function only**: `int main() { ... }`. No user-defined functions yet.
- **Type**: `int` only.
- **Operators**: `+ - * / % == != < > <= >=`. Standard C precedence applies.
- **Variables**: declare with `int name;`, assign with `name = expr;`. Assignment chaining (`a = b = 3;`) must work.
- **Control flow**: `if`/`else` and `while`.
- **I/O**: `print_int(int x)` prints the integer followed by a newline.
- **Return**: `return expr;` terminates the program, returning that value as the exit code.
- **Error handling**: on division by zero, use of an uninitialized variable, or other runtime error, print a message to stderr and exit with code 1.
- **`#include`**: should be silently ignored if present.

## Not in this phase

Arrays, pointers, `malloc`, global variables, user-defined functions, `for`, `break`, `continue`.

## Example

`hello.c`:
```c
int main() {
    int x;
    x = 10;
    if (x > 5) {
        print_int(x);
    } else {
        print_int(0);
    }
    return 0;
}
```

```bash
$ ./cinterp hello.c
10
$ echo $?
0
```
