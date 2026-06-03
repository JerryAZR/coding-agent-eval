#!/usr/bin/env python3
import sys, json, re, collections

LOG_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (ERROR|WARN|INFO|DEBUG) (.*)$')

def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(1)

    level_filter = None
    group_by = None
    file_path = None

    i = 0
    while i < len(args):
        if args[i] == '--level':
            i += 1
            if i >= len(args):
                sys.exit(1)
            level_filter = args[i]
            i += 1
        elif args[i] == '--group-by':
            i += 1
            if i >= len(args):
                sys.exit(1)
            group_by = args[i]
            i += 1
        else:
            file_path = args[i]
            i += 1

    if not file_path:
        sys.exit(1)

    lines = []
    with open(file_path) as f:
        for line in f:
            line = line.rstrip('\n')
            m = LOG_RE.match(line)
            if not m:
                continue
            ts, level, msg = m.groups()
            lines.append((ts, level, msg))

    if level_filter:
        if level_filter not in ('ERROR', 'WARN', 'INFO', 'DEBUG'):
            sys.exit(1)
        for ts, level, msg in lines:
            if level == level_filter:
                print(f"{ts} {level} {msg}")
        return

    if group_by == 'hour':
        counts = collections.Counter()
        for ts, level, msg in lines:
            hour = ts[:13]
            counts[hour] += 1
        print(json.dumps(dict(counts), sort_keys=True))
        return

    counts = collections.Counter()
    for ts, level, msg in lines:
        counts[level] += 1
    print(json.dumps(dict(counts), sort_keys=True))

if __name__ == '__main__':
    main()
