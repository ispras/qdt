#include <stdio.h>
#include <stdint.h>

void print_float(float f)
{
    float _f = f;
    uint32_t u = *(uint32_t*)&_f;
    printf("%e %u 0x%x", f, u, u);
}

#define PRINT_FOP(A, OP, B) do { \
    float _PRINT_FOP_c = (A) OP (B); \
    print_float(A); \
    printf(" " #OP " "); \
    print_float(B); \
    printf(" = "); \
    print_float(_PRINT_FOP_c); \
} while ((0))

#define PRINTLN_FOP(...) do { \
    PRINT_FOP(__VA_ARGS__); \
    printf("\n"); \
} while ((0))

void print_double(double f)
{
    double _f = f;
    uint64_t u = *(uint64_t*)&_f;
    printf("%le %lu 0x%lx", f, u, u);
}

#define PRINT_DOP(A, OP, B) do { \
    double _PRINT_DOP_c = (A) OP (B); \
    print_double(A); \
    printf(" " #OP " "); \
    print_double(B); \
    printf(" = "); \
    print_double(_PRINT_DOP_c); \
} while ((0))

#define PRINTLN_DOP(...) do { \
    PRINT_DOP(__VA_ARGS__); \
    printf("\n"); \
} while ((0))

void main(void)
{
    PRINTLN_FOP(-1.448528141878569e-08, /, -72498544640.0);
    PRINTLN_DOP(-4.562228484338099e+252, -, 1.370898521487079e+56);
    PRINTLN_DOP(2.5774648840236446e-169, +, -1.7333702738031197e+296);
}

