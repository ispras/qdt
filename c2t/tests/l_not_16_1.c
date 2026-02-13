/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int16_t a = 0x9084, c;

    c = ~a;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
