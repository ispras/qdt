/* Like the example in DWARFv4 */
typedef struct {
    int j :5;
    int k :6;
    int m :5;
    int n :8;
} S;

/* Bit fields are not at the structure beginning */
typedef struct {
    int pad4;
    short pad2;
    char pad1;
    int a :7;
    int b :15;
    int c :8;
} S2;

int main(int argc, char **argv)
{
    S2 s2;

    s2.a = 5;
    s2.b = 6;
    s2.c = 7;

    S s;
    s.j = 1;
    s.k = 2;
    s.m = 3;
    s.n = 4;
    return 0;
}
