/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile float a = -1.448528141878569e-08, b = -72498544640.0, c;

    c = a / b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
