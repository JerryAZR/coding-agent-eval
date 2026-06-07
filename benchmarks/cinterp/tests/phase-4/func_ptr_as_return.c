int add(int a, int b) {
    return a + b;
}

int mul(int a, int b) {
    return a * b;
}

int (*choose_op(int n))(int, int) {
    if (n == 0) {
        return add;
    }
    return mul;
}

int main() {
    int (*f)(int, int);
    f = choose_op(0);
    print_int(f(1, 2));
    f = choose_op(1);
    print_int(f(1, 2));
    return 0;
}
