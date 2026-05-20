/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile double
        a = 2.5774648840236446e-169,
        b = -1.7333702738031197e+296,
        c;

    c = a + b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
