int main() {
    int x;
    int *p;
    int **pp;
    x = 7;
    p = &x;
    pp = &p;
    print_int(**pp);
    return 0;
}
