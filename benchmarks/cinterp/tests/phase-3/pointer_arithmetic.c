int main() {
    int arr[3];
    int *p;
    arr[0] = 10;
    arr[1] = 20;
    arr[2] = 30;
    p = arr;
    *(p + 1) = 99;
    print_int(arr[0]);
    print_int(arr[1]);
    print_int(arr[2]);
    return 0;
}
