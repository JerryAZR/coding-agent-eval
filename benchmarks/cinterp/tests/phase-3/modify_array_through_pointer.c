void set_second(int *a, int val) {
    a[1] = val;
}

int main() {
    int arr[3];
    arr[0] = 0;
    arr[1] = 0;
    arr[2] = 0;
    set_second(arr, 99);
    print_int(arr[0]);
    print_int(arr[1]);
    print_int(arr[2]);
    return 0;
}
