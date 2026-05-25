/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int32_t a = 0xd2835f1, b = 0xa, c;

    c = a << b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
