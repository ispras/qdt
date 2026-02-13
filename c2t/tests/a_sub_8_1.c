/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int8_t a = 0xe3, b = 0xb9, c;

    c = a - b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
