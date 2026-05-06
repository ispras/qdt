/* Control flow instruction */

#include "common.h"

float func(float a0, float a1, float a2, float a3, float a4,
    float a5, float a6, float a7, float a8, float a9,
    float a10, float a11, float a12, float a13, float a14,
    float a15, float a16, float a17, float a18, float a19,
    float a20, float a21, float a22, float a23, float a24,
    float a25, float a26, float a27, float a28, float a29,
    float a30, float a31, float a32, float a33, float a34,
    float a35, float a36, float a37, float a38, float a39,
    float a40, float a41, float a42, float a43, float a44,
    float a45, float a46, float a47, float a48, float a49
) {
    return a0 + a1 + a2 + a3 + a4 + a5 + a6 + a7 + a8 + a9 + a10 + a11 + a12 +
        a13 + a14 + a15 + a16 + a17 + a18 + a19 + a20 + a21 + a22 + a23 + a24 +
        a25 + a26 + a27 + a28 + a29 + a30 + a31 + a32 + a33 + a34 + a35 + a36 +
        a37 + a38 + a39 + a40 + a41 + a42 + a43 + a44 + a45 + a46 + a47 + a48 +
        a49;
}

void main(void)
{
    volatile float
        a0 = 1.0,
        a1 = 2.0,
        a2 = 3.0,
        a3 = 4.0,
        a4 = 5.0,
        a5 = 6.0,
        a6 = 7.0,
        a7 = 8.0,
        a8 = 9.0,
        a9 = 10.0,
        a10 = 11.0,
        a11 = 12.0,
        a12 = 13.0,
        a13 = 14.0,
        a14 = 15.0,
        a15 = 16.0,
        a16 = 17.0,
        a17 = 18.0,
        a18 = 19.0,
        a19 = 20.0,
        a20 = 21.0,
        a21 = 22.0,
        a22 = 23.0,
        a23 = 24.0,
        a24 = 25.0,
        a25 = 26.0,
        a26 = 27.0,
        a27 = 28.0,
        a28 = 29.0,
        a29 = 30.0,
        a30 = 31.0,
        a31 = 32.0,
        a32 = 33.0,
        a33 = 34.0,
        a34 = 35.0,
        a35 = 36.0,
        a36 = 37.0,
        a37 = 38.0,
        a38 = 39.0,
        a39 = 40.0,
        a40 = 41.0,
        a41 = 42.0,
        a42 = 43.0,
        a43 = 44.0,
        a44 = 45.0,
        a45 = 46.0,
        a46 = 47.0,
        a47 = 48.0,
        a48 = 49.0,
        a49 = 50.0,
        c;

    c = func(a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14,
        a15, a16, a17, a18, a19, a20, a21, a22, a23, a24, a25, a26, a27, a28,
        a29, a30, a31, a32, a33, a34, a35, a36, a37, a38, a39, a40, a41, a42,
        a43, a44, a45, a46, a47, a48, a49
    );
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
