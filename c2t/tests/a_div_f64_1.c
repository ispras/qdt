/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile double a = 4.0690390574653988e-188, b = 3.4285662889134074e-298, c;

    c = a / b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
