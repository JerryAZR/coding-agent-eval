# Extend Your C Interpreter with Function Pointers

Your task is to extend `cinterp` so functions can be treated as values.

## Deliverable

The same executable: `./cinterp`

## What to Add

1. **Function pointer variables**:
   ```c
   int subtract(int a, int b) {
       return a - b;
   }

   int main() {
       int (*op)(int, int);
       op = subtract;
       print_int(op(10, 3));
       return 0;
   }
   ```

2. **Function pointers as function arguments**:
   ```c
   int compute(int (*fn)(int, int), int a, int b) {
       return fn(a, b);
   }

   int main() {
       print_int(compute(subtract, 8, 2));
       return 0;
   }
   ```

3. **Function pointers in arrays**:
   ```c
   int (*handlers[3])(int, int);
   handlers[0] = subtract;
   handlers[1] = divide;
   print_int(handlers[0](5, 1));
   ```

4. **Function pointer as return value**:
   ```c
   int (*pick(int mode))(int, int) {
       if (mode == 0) return subtract;
       return divide;
   }

   int main() {
       int (*f)(int, int);
       f = pick(0);
       print_int(f(7, 2));
       return 0;
   }
   ```

5. **Null function pointers**:
   ```c
   int (*f)(int, int);
   f = 0;
   ```
   Calling a null function pointer is a runtime error.

## Rules

- Function pointer types must match the target function's signature exactly (same return type, same parameter types and count).
- Assigning a function name to a function pointer variable stores a reference to that function.
- Calling through a function pointer behaves exactly like a direct call.
- All prior phases must continue to work.

## Error cases

Your interpreter must detect and report as runtime errors:
- Calling a null function pointer
- Passing the wrong number of arguments to a function

## Not in this phase

`typedef`, `struct`, `union`, `enum`, `char` and strings, `malloc`, `void*`.
