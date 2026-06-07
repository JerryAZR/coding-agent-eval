int sum(int *a, int n) {
    int i;
    int total;
    total = 0;
    i = 0;
    while (i < n) {
        total = total + a[i];
        i = i + 1;
    }
    return total;
}

int main() {
    int arr[3];
    arr[0] = 1;
    arr[1] = 2;
    arr[2] = 3;
    print_int(sum(arr, 3));
    return 0;
}
