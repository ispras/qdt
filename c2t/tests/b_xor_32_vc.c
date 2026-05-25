/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int32_t a = 0x5a0b36f7, c;

    c = a ^ 15;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
