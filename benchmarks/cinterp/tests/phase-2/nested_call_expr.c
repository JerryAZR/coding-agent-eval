int mul(int a, int b) {
    return a * b;
}

int add(int a, int b) {
    return a + b;
}

int main() {
    print_int(add(mul(2, 3), 4));
    return 0;
}
