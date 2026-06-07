# Build a Python Compiler

Your task is to build a compiler for a restricted subset of Python. The compiler reads a `.py` file and produces a native executable.

## Deliverable

Single executable: `./pyc`

## Interface

```
./pyc <program.py>
```

After running `./pyc`, a native executable named `a.out` must exist in the current directory. Running `./a.out` executes the compiled program.

## How to Build the Executable

You may emit any of the following:
- x86-64 machine code and write an ELF executable directly
- x86-64 assembly and invoke the system assembler (`as`) and linker (`ld`)
- C, C++, or Rust source code and invoke the system compiler (`gcc`, `clang`, `rustc`)
- Bytecode for a custom VM, and bundle the VM runtime into the executable

You must **not** embed a Python interpreter, use PyInstaller, Nuitka, or any tool that packages an interpreter inside the binary. The produced executable must be the result of compiling the input Python program, not a self-extracting archive.

## Phase 1 Language Subset

Your compiler must handle the following syntax:

- **Integer literals**: `42`, `-7` (unary minus)
- **Arithmetic operators**: `+`, `-`, `*`, `//` (floor division), `%`, `**` (exponentiation)
- **Comparison operators**: `==`, `!=`, `<`, `>`, `<=`, `>=`
- **Boolean operators**: `and`, `or`, `not`
- **Variables**: assignment and use. Assignment chaining (`a = b = 3`) must work.
- **Control flow**: `if` / `elif` / `else`, `while`
- **Loop control**: `break`, `continue`
- **I/O**: `print_int(x)` prints the integer `x` followed by a single newline
- **Exit**: `sys.exit(n)` terminates the program with exit code `n`

## Operator Precedence

Follow Python precedence: `**` highest, then unary `+`/`-`, then `*`, `//`, `%`, then `+`, `-`, then comparisons, then `not`, then `and`, then `or`.

## Example

Input `hello.py`:
```python
x = 10
if x > 5:
    print_int(x)
else:
    print_int(0)
sys.exit(0)
```

Command:
```bash
$ ./pyc hello.py
$ ./a.out
10
$ echo $?
0
```

## Error Cases

On runtime error (division by zero, etc.), print a brief error message and exit with code 1.

## Not in this phase

Functions (`def`), lists, dictionaries, strings, floats, classes, imports, exceptions, generators, decorators.
