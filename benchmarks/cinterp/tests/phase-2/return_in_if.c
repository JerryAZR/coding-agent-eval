int abs(int x) {
    if (x < 0) {
        return -x;
    }
    return x;
}

int main() {
    print_int(abs(-7));
    print_int(abs(3));
    return 0;
}
