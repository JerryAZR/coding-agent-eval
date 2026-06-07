# Extend Your C Interpreter with Functions

Your task is to extend `cinterp` so it supports user-defined functions.

## Deliverable

The same executable: `./cinterp`

## Interface

```
./cinterp <program.c>
```

Behavior is unchanged from Phase 1: execute the program, print `print_int` output to stdout, return the `main` return value as the process exit code, and exit with code 1 on runtime error (printing a brief message to stderr).

## What to Add

1. **User-defined functions**:
   ```c
   int foo(int a, int b) {
       int tmp;
       tmp = a + b;
       return tmp;
   }
   ```

2. **Function calls** from any function, including `main`:
   ```c
   int result;
   result = foo(3, 4);
   print_int(result);
   ```

3. **Recursion** must work. Functions are called by name only; **function pointers are not required**.

4. **Parameters and local variables** are scoped to the function they are declared in.

5. **Return statement** works in any function, not just `main`.

## Rules

- The entry point is still `int main() { ... }`.
- Functions may be defined in any order.
- All parameters are passed by value.
- Return type is always `int`.
- `main` still returns the process exit code.
- All Phase 1 features must continue to work.

## Not in this phase

Arrays, pointers, `malloc`, global variables, `for`, `break`, `continue`, varargs, static local variables.

## Example

```c
int add(int a, int b) {
    return a + b;
}

int main() {
    int x;
    x = add(3, 4);
    print_int(x);
    return 0;
}
```

```bash
$ ./cinterp example.c
7
$ echo $?
0
```
