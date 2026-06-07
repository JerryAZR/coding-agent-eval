int compute() {
    int i;
    int sum;
    sum = 0;
    i = 0;
    while (i < 5) {
        if (i % 2 == 0) {
            sum = sum + i;
        }
        i = i + 1;
    }
    return sum;
}

int main() {
    print_int(compute());
    return 0;
}
