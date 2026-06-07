int main() {
    int x;
    int *p;
    x = 10;
    p = &x;
    *p = 42;
    print_int(x);
    return 0;
}
