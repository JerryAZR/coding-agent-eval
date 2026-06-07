int main() {
    int arr[5];
    int i;
    i = 0;
    while (i < 5) {
        arr[i] = i * 2;
        i = i + 1;
    }
    i = 0;
    while (i < 5) {
        print_int(arr[i]);
        i = i + 1;
    }
    return 0;
}
