/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile double a = 4.069039057465399e-188, b = 3.4285662889134074e-298, c;

    c = a * b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
