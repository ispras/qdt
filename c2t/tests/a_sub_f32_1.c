/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile float a = -1.8000596102524e+22, b = 0x58bac230, c;

    c = a - b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
