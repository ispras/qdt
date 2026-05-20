/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int16_t a = 0xdd91, b = 0xfe43, c;

    c = a - b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
