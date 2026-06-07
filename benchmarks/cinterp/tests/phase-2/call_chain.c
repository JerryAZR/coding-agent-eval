int c() {
    return 3;
}

int b() {
    return c() + 2;
}

int a() {
    return b() + 1;
}

int main() {
    print_int(a());
    return 0;
}
