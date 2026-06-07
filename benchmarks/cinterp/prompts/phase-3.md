# Extend Your C Interpreter with Arrays and Pointers

Your task is to extend `cinterp` so it supports arrays, pointers, and address arithmetic.

## Deliverable

The same executable: `./cinterp`

## Language Features to Add

Your interpreter must support the following syntax and semantics.

### Arrays

- **Declaration:** `int name[constant];` where `constant` is a positive integer literal known at parse time. The array is local to the function it is declared in.
- **Indexing:** `name[index]` where `index` is any `int` expression. This reads or writes the element at position `index` (0-based).

### Pointers

- **Declaration:** `int *name;` declares a pointer to `int`.
- **Address-of:** `&variable` produces a pointer to the named variable. `&array[index]` produces a pointer to that array element.
- **Dereference:** `*pointer` reads or writes the value at the address stored in the pointer.
- **Pointer arithmetic:** `*(pointer + offset)` accesses the element `offset` positions away from the pointer, where each position is one `int` (not one byte).
- **Null pointer:** Assigning `0` to a pointer variable makes it null. Dereferencing a null pointer is a runtime error.

### Pointer-to-Pointer

- **Declaration:** `int **name;` declares a pointer to a pointer to `int`. Multiple levels of dereference (`**pp`, `*pp`, etc.) must resolve to the underlying `int`.

### Array Decay

- When an array name appears in a context that expects a pointer (for example, as a function argument where the parameter is `int *a`), the array name is treated as a pointer to its first element.

## Error Cases

Your interpreter must detect and report as runtime errors:
- Dereferencing a null pointer
- Passing the wrong number of arguments to a function

Test programs will only dereference pointers obtained from `&`, array names, or `0` (null).

## Prior Phases

All features from Phases 1 and 2 must continue to work.

## Not in this phase

`malloc`, `free`, `char` and strings, function pointers, pointer arithmetic on non-array pointers (e.g., `&x + 1`).
