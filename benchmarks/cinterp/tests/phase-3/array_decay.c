int first(int *a) {
    return a[0];
}

int main() {
    int arr[3];
    arr[0] = 7;
    arr[1] = 8;
    arr[2] = 9;
    print_int(first(arr));
    return 0;
}
