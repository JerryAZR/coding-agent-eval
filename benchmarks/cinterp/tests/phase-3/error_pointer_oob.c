int main() {
    int arr[3];
    int *p;
    p = arr;
    *(p + 3) = 1;
    return 0;
}
