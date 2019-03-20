/* Like the example in DWARFv4 */
typedef struct {
    int j :5;
    int k :6;
    int m :5;
    int n :8;
} S;

int main(int argc, char **argv)
{
    S s;
    s.j = 1;
    s.k = 2;
    s.m = 3;
    s.n = 4;
    return 0;
}
