/* Control flow instruction */

#include <stdint.h>

uint16_t func(uint16_t a0, uint16_t a1, uint16_t a2, uint16_t a3, uint16_t a4,
    uint16_t a5, uint16_t a6, uint16_t a7, uint16_t a8, uint16_t a9,
    uint16_t a10, uint16_t a11, uint16_t a12, uint16_t a13, uint16_t a14,
    uint16_t a15, uint16_t a16, uint16_t a17, uint16_t a18, uint16_t a19,
    uint16_t a20, uint16_t a21, uint16_t a22, uint16_t a23, uint16_t a24,
    uint16_t a25, uint16_t a26, uint16_t a27, uint16_t a28, uint16_t a29,
    uint16_t a30, uint16_t a31, uint16_t a32, uint16_t a33, uint16_t a34,
    uint16_t a35, uint16_t a36, uint16_t a37, uint16_t a38, uint16_t a39,
    uint16_t a40, uint16_t a41, uint16_t a42, uint16_t a43, uint16_t a44,
    uint16_t a45, uint16_t a46, uint16_t a47, uint16_t a48, uint16_t a49
) {
    return a0 + a1 + a2 + a3 + a4 + a5 + a6 + a7 + a8 + a9 + a10 + a11 + a12 +
        a13 + a14 + a15 + a16 + a17 + a18 + a19 + a20 + a21 + a22 + a23 + a24 +
        a25 + a26 + a27 + a28 + a29 + a30 + a31 + a32 + a33 + a34 + a35 + a36 +
        a37 + a38 + a39 + a40 + a41 + a42 + a43 + a44 + a45 + a46 + a47 + a48 +
        a49;
}

void main(void)
{
    volatile uint16_t a0 = 1, a1 = 2, a2 = 3, a3 = 4, a4 = 5, a5 = 6, a6 = 7,
        a7 = 8, a8 = 9, a9 = 10, a10 = 11, a11 = 12, a12 = 13, a13 = 14,
        a14 = 15, a15 = 16, a16 = 17, a17 = 18, a18 = 19, a19 = 20, a20 = 21,
        a21 = 22, a22 = 23, a23 = 24, a24 = 25, a25 = 26, a26 = 27, a27 = 28,
        a28 = 29, a29 = 30, a30 = 31, a31 = 32, a32 = 33, a33 = 34, a34 = 35,
        a35 = 36, a36 = 37, a37 = 38, a38 = 39, a39 = 40, a40 = 41, a41 = 42,
        a42 = 43, a43 = 44, a44 = 45, a45 = 46, a46 = 47, a47 = 48, a48 = 49,
        a49 = 50, c;

    c = func(a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14,
        a15, a16, a17, a18, a19, a20, a21, a22, a23, a24, a25, a26, a27, a28,
        a29, a30, a31, a32, a33, a34, a35, a36, a37, a38, a39, a40, a41, a42,
        a43, a44, a45, a46, a47, a48, a49
    );
    c = 0;     //$ch.c

    return;    //$bre
}
