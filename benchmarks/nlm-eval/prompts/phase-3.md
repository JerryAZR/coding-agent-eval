# Phase 3: Grouped Operations

Extend `nlm-eval` to support parentheses:

```
./nlm-eval NUM1 plus '(' NUM2 minus NUM3 ')'
```

Parentheses may be nested. Parentheses are passed as separate
arguments (the shell will see them as literal `(` and `)` tokens).

Example:
```
./nlm-eval 10 minus '(' 3 plus 2 ')'
```
should print `5` (because 10 - (3 + 2) = 5).

Exit 0 on success, non-zero on invalid input.
