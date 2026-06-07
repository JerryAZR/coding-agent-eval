int dup(int x) {
    return x + x;
}

int main() {
    int x;
    x = 5;
    print_int(dup(3));
    print_int(x);
    return 0;
}
