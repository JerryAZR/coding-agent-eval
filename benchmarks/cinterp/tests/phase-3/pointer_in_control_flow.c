int main() {
    int x;
    int y;
    int *p;
    x = 5;
    y = 10;
    p = &x;
    if (*p > 3) {
        p = &y;
        *p = 20;
    }
    print_int(x);
    print_int(y);
    return 0;
}
