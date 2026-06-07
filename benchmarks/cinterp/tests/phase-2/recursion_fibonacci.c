int fib(int n) {
    if (n <= 1) {
        return n;
    }
    return fib(n - 1) + fib(n - 2);
}

int main() {
    print_int(fib(0));
    print_int(fib(1));
    print_int(fib(6));
    return 0;
}
