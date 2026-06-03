# Test draft

## 1. Natural Language Math Eval (CLI tool)

### 1.1 Simple evaluations

The binary must be named `nlm-eval`, and support operations like

```
./nlm-eval NUM1 plus/minus NUM2
```
where NUM1 and NUM2 can be any real numbers

It should print the result and return 0 on success.

The tests would test things like

- `./nlm-eval 1 plus 2` (expects `3`)
- `./nlm-eval 1.5 plus 1.5` (expects `3`)

### 1.2 Long Operations

```
./nlm-eval NUM1 plus/minus NUM2 plus/minus NUM3 ...
```

### 1.3 Grouped Operations

```
./nlm-eval NUM1 plus/minus (NUM2 plus/minus NUM3) ...
```

...

## 1. Natural Language Math Eval (CLI tool)
