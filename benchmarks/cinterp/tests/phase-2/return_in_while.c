int first_positive(int a, int b, int c) {
    if (a > 0) return a;
    if (b > 0) return b;
    if (c > 0) return c;
    return 0;
}

int main() {
    print_int(first_positive(-1, -2, 5));
    print_int(first_positive(3, -1, 2));
    print_int(first_positive(-1, -2, -3));
    return 0;
}
