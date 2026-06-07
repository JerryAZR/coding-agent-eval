int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

int main() {
    print_int(factorial(1));
    print_int(factorial(5));
    return 0;
}
