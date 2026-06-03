# Phase 2: Chained Operations

Extend `nlm-eval` to support chained left-associative operations:

```
./nlm-eval NUM1 plus NUM2 minus NUM3 plus NUM4 ...
```

Any sequence of `plus` and `minus` with any number of operands.
Operations are evaluated left to right.

Example:
```
./nlm-eval 10 minus 3 plus 2
```
should print `9` (because (10 - 3) + 2 = 9).

Exit 0 on success, non-zero on invalid input.
