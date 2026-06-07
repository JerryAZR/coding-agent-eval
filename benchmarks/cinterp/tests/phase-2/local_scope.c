int foo() {
    int x;
    x = 99;
    return x;
}

int main() {
    int x;
    x = 1;
    print_int(foo());
    print_int(x);
    return 0;
}
