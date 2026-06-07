int main() {
    int (*f)(int, int);
    f = 0;
    print_int(f(1, 2));
    return 0;
}
