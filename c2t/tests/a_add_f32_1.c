/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile float a = 20363956191232.0, b = 1270141312.0, c;

    c = a + b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
