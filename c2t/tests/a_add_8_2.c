/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int8_t a = 0x4e, *b, c;
    b = &a;

    c = a + *b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
