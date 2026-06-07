# Extend Your C Interpreter with Arrays and Pointers

Your task is to extend `cinterp` so it supports arrays, pointers, and address arithmetic.

## Deliverable

The same executable: `./cinterp`

## What to Add

1. **Arrays**:
   ```c
   int arr[10];
   arr[0] = 5;
   print_int(arr[0]);
   ```

2. **Pointers**:
   ```c
   int x;
   int *p;
   p = &x;
   *p = 42;
   print_int(x);
   ```

3. **Pointer arithmetic**:
   ```c
   int arr[3];
   int *p;
   p = arr;
   *(p + 1) = 99;
   print_int(arr[1]);
   ```

4. **Arrays in function calls** (array-to-pointer decay):
   ```c
   int sum(int *a, int n) {
       int i;
       int total;
       total = 0;
       i = 0;
       while (i < n) {
           total = total + a[i];
           i = i + 1;
       }
       return total;
   }

   int main() {
       int arr[3];
       arr[0] = 1;
       arr[1] = 2;
       arr[2] = 3;
       print_int(sum(arr, 3));
       return 0;
   }
   ```

5. **Pointer-to-pointer**:
   ```c
   int x;
   int *p;
   int **pp;
   x = 7;
   p = &x;
   pp = &p;
   print_int(**pp);
   ```

6. **Null pointers**:
   ```c
   int *p;
   p = 0;
   ```
   Dereferencing a null pointer is a runtime error.

## Rules

- Arrays are declared with a constant size: `int arr[10];`. The size is known at parse time.
- Pointer arithmetic `*(p + n)` works in units of `int` (so `*(p + 1)` refers to the next integer, not the next byte).
- `&x` produces a pointer to variable `x`. `&arr[i]` produces a pointer to the i-th element.
- All prior phases must continue to work.

## Error cases

Your interpreter must detect and report as runtime errors:
- Dereferencing a null pointer
- Passing the wrong number of arguments to a function

Test programs will only dereference pointers obtained from `&`, array names, or `0` (null).
## Not in this phase

`malloc`, `free`, `char` and strings, function pointers, pointer arithmetic on non-array pointers (e.g., `&x + 1`).
