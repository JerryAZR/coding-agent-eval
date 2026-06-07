# Extend Your C Interpreter with Arrays and Pointers

Your task is to extend `cinterp` so it supports arrays, pointers, and address arithmetic.

## Deliverable

The same executable: `./cinterp`

## What to Add

1. **Arrays**:
   ```c
   int nums[5];
   nums[2] = 7;
   print_int(nums[2]);
   ```

2. **Pointers**:
   ```c
   int value;
   int *ptr;
   ptr = &value;
   *ptr = 100;
   print_int(value);
   ```

3. **Pointer arithmetic**:
   ```c
   int data[4];
   int *p;
   p = data;
   *(p + 2) = 42;
   print_int(data[2]);
   ```

4. **Arrays in function calls** (array-to-pointer decay):
   ```c
   int count(int *vals, int n) {
       int i;
       int total;
       total = 0;
       i = 0;
       while (i < n) {
           total = total + vals[i];
           i = i + 1;
       }
       return total;
   }

   int main() {
       int vals[3];
       vals[0] = 10;
       vals[1] = 20;
       vals[2] = 30;
       print_int(count(vals, 3));
       return 0;
   }
   ```

5. **Pointer-to-pointer**:
   ```c
   int n;
   int *q;
   int **r;
   n = 99;
   q = &n;
   r = &q;
   print_int(**r);
   ```

6. **Null pointers**:
   ```c
   int *ptr;
   ptr = 0;
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
