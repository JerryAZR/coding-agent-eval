#!/usr/bin/env python3
import sys

def parse_num(s):
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"not a number: {s}")

def main():
    tokens = sys.argv[1:]
    if len(tokens) < 3:
        sys.exit(1)

    stack = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == '(':
            stack.append('(')
            i += 1
        elif tok == ')':
            if len(stack) < 2 or stack[-2] != '(':
                sys.exit(1)
            val = stack[-1]
            stack = stack[:-2]
            if stack and stack[-1] != '(':
                op = stack.pop()
                left = stack.pop()
                if op == 'plus':
                    val = left + val
                elif op == 'minus':
                    val = left - val
                else:
                    sys.exit(1)
            stack.append(val)
            i += 1
        elif tok in ('plus', 'minus'):
            if len(stack) < 1:
                sys.exit(1)
            stack.append(tok)
            i += 1
        else:
            num = parse_num(tok)
            if stack and stack[-1] != '(':
                if len(stack) < 2:
                    sys.exit(1)
                op = stack.pop()
                left = stack.pop()
                if op == 'plus':
                    num = left + num
                elif op == 'minus':
                    num = left - num
                else:
                    sys.exit(1)
            stack.append(num)
            i += 1

    if len(stack) != 1:
        sys.exit(1)
    result = stack[0]
    if result == int(result):
        print(int(result))
    else:
        print(result)

if __name__ == '__main__':
    main()
