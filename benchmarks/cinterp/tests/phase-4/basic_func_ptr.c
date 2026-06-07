int add(int a, int b) {
    return a + b;
}

int main() {
    int (*f)(int, int);
    f = add;
    print_int(f(3, 4));
    return 0;
}
