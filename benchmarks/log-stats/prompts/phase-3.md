# Phase 3: Hourly Aggregation

Extend `log-stats` to support hourly aggregation.

Usage:
```
./log-stats --group-by hour FILE
```

Group log entries by the hour portion of their timestamp and count how many entries fall into each hour.

Print a JSON object to stdout mapping hour strings to counts:
```json
{"2024-01-01 00": 5, "2024-01-01 01": 3}
```

Hours are formatted as `YYYY-MM-DD HH` (24-hour clock).
Only include hours that have at least one entry.
Exit 0 on success, non-zero on error.
