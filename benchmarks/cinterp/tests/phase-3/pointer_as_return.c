int *get_ptr(int *arr) {
    return arr + 1;
}

int main() {
    int arr[3];
    int *p;
    arr[0] = 10;
    arr[1] = 20;
    arr[2] = 30;
    p = get_ptr(arr);
    print_int(*p);
    return 0;
}
