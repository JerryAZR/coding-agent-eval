int add(int a, int b) {
    return a + b;
}

int mul(int a, int b) {
    return a * b;
}

int main() {
    int (*ops[2])(int, int);
    ops[0] = add;
    ops[1] = mul;
    print_int(ops[0](3, 4));
    print_int(ops[1](3, 4));
    return 0;
}
