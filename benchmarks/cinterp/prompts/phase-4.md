# Extend Your C Interpreter with Function Pointers

Your task is to extend `cinterp` so functions can be treated as values.

## Deliverable

The same executable: `./cinterp`

## Language Features to Add

Your interpreter must support the following syntax and semantics.

### Function Pointer Variables

- **Declaration:** `int (*name)(int, int);` declares a variable that can hold a reference to any function with the signature `int f(int, int)`.
- **Assignment:** `name = func_name;` stores a reference to the named function in the variable.
- **Indirect call:** `name(args...)` invokes the function currently stored in the pointer, with the same behavior as a direct call.

### Function Pointers in Other Contexts

- **As parameters:** A function may accept a function pointer as an argument. For example, a parameter declared as `int (*op)(int, int)` receives a function reference.
- **As return values:** A function may return a function pointer. For example, `int (*choose(int mode))(int, int)` is a function that returns a pointer to a function taking two `int`s and returning `int`.
- **In arrays:** An array of function pointers is declared as `int (*name[3])(int, int);`. Elements are assigned and called as `name[i](args...)`.

### Null Function Pointers

- Assigning `0` to a function pointer variable makes it null. Calling a null function pointer is a runtime error.

### Signature Matching

- A function pointer can only be assigned a function whose return type and parameter types and count match exactly. The interpreter does not need to support implicit conversions or variadic functions.

## Error Cases

Your interpreter must detect and report as runtime errors:
- Calling a null function pointer
- Passing the wrong number of arguments to a function

## Prior Phases

All features from Phases 1, 2, and 3 must continue to work.

## Not in this phase

`typedef`, `struct`, `union`, `enum`, `char` and strings, `malloc`, `void*`.
