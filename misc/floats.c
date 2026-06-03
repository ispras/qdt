#include <stdio.h>
#include <stdint.h>

void print_float(float f)
{
    float _f = f;
    uint32_t u = *(uint32_t*)&_f;
    printf("%.8e %u 0x%x", f, u, u);
}

#define U32_F(U) ({ \
    uint32_t _U32_F_tmp_u = (U); \
    *(float*)&_U32_F_tmp_u; \
    })

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

#define U64_D(U) ({ \
    uint64_t _U64_D_tmp_u = (U); \
    *(double*)&_U64_D_tmp_u; \
    })

void print_double(double f)
{
    double _f = f;
    uint64_t u = *(uint64_t*)&_f;
    printf("%.16le %lu 0x%lx", f, u, u);
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

#define NL printf("\n")

int clz8(uint8_t u) {
    if (u & 0x80) return 0;
    if (u & 0x40) return 1;
    if (u & 0x20) return 2;
    if (u & 0x10) return 3;
    if (u & 0x08) return 4;
    if (u & 0x04) return 5;
    if (u & 0x02) return 6;
    if (u & 0x01) return 7;
    return 8;
}

int clz16(uint16_t u)
{
    int r = clz8(u >> 8);
    return (r == 8) ? (8 + clz8(u)) : r;
}

int clz32(uint32_t u)
{
    int r = clz16(u >> 16);
    return (r == 16) ? (16 + clz16(u)) : r;
}

int clz64(uint64_t u)
{
    int r = clz32(u >> 32);
    return (r == 32) ? (32 + clz32(u)) : r;
}

double uint64_to_double_manual(uint64_t u)
{
    if (u == 0) return 0.0;

    int leading_zeros = clz64(u);
    int exponent = 63 - leading_zeros;
    uint64_t mantissa = u;

    if (exponent > 52) {
        // extract mantissa
        int shift = exponent - 52;
        mantissa >>= shift;
        // round up
        if ((u << (64 - shift)) != 0) {
            mantissa += 1;
        }
    }

    // build double: sign=0, exp=exponent+1023, mantissa
    uint64_t bits = (
        (uint64_t)(exponent + 1023) << 52)
      | (mantissa & 0x000FFFFFFFFFFFFF);
    return U64_D(bits);
}

void main(void)
{
    PRINTLN_FOP(-1.448528141878569e-08, /, -72498544640.0);
    PRINTLN_DOP(-4.562228484338099e+252, -, 1.370898521487079e+56);
    PRINTLN_DOP(2.5774648840236446e-169, +, -1.7333702738031197e+296);
    PRINTLN_DOP(U64_D(0xbf72a7ddffffffff), *, U64_D(0xbc0f1b5e20000000));
    PRINTLN_FOP(U32_F(0xbf72a7dd), *, U32_F(0xbf870a00));
    PRINTLN_FOP(U32_F(0x40000000), -, U32_F(0x3f800000));
    print_double((double)(U32_F(0xb278daf1)));
    NL;
    PRINTLN_DOP(U32_F(0xbf870a00), *, U32_F(0xbf72a7dd));
    PRINTLN_DOP(U64_D(0x4000000000000000), -, U64_D(0x3ff0000003344000));
    PRINTLN_DOP(U64_D(0x3feffffff9978000), *, U32_F(0xbf72a7dd));
    PRINTLN_DOP(U64_D(0xbfee54fb99ed034c), *, U32_F(0xbf870a00));
    PRINTLN_DOP(U64_D(0x4000000000000000), -, U64_D(0x3feffffffffffffe));
    PRINTLN_DOP(U64_D(0xbfee54fb99ed034c), *, U64_D(0x3ff0000000000001));
    PRINTLN_DOP(4.069039057465399e-188, /, 3.4285662889134074e-298);
    print_double(U64_D(0x56d0000000000000)); NL;
    print_double(0x87654321abcdef09); NL;
    print_double(uint64_to_double_manual(0x87654321abcdef09)); NL;
    PRINTLN_DOP(U64_D(0x43e0eca8643579be), -, U64_D(0x43e0eca8643579bd));
    print_double(0x7654321abcdef09); NL;
    print_double(uint64_to_double_manual(0x7654321abcdef09)); NL;
    PRINTLN_DOP(4.069039057465399e-188, /, 3.4285662889134074e-298);
    print_double(U64_D(0x56d0000000000000)); NL;
    print_float((float)1.0e+10); NL;
    print_double((double)(float)1.0e+20); NL;
}

