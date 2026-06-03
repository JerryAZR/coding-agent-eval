# Phase 1: Count Log Levels

Build a CLI tool named `log-stats`.

It reads a log file and counts occurrences of each log level.

Log lines have this format:
```
YYYY-MM-DD HH:MM:SS LEVEL message text
```

`LEVEL` is one of: `ERROR`, `WARN`, `INFO`, `DEBUG`

Usage:
```
./log-stats FILE
```

It must print a JSON object to stdout with the count of each level found:
```json
{"ERROR": 5, "WARN": 2, "INFO": 10, "DEBUG": 0}
```

Only include levels that appear in the file. Exit 0 on success, non-zero on error.
