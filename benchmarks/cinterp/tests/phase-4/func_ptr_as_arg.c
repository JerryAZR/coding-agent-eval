int add(int a, int b) {
    return a + b;
}

int apply(int (*op)(int, int), int x, int y) {
    return op(x, y);
}

int main() {
    print_int(apply(add, 5, 6));
    return 0;
}
