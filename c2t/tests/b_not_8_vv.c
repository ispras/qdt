/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int8_t a = 0xb5, c;

    c = ~a;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
