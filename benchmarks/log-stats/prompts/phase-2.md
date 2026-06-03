# Phase 2: Filter by Level

Extend `log-stats` to support filtering by log level.

Usage:
```
./log-stats --level LEVEL FILE
```

Print only lines matching the given level, one per line, in the original order.

Example:
```
./log-stats --level ERROR app.log
```

Exit 0 on success, non-zero on error (including invalid LEVEL).
