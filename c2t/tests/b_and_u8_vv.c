/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint8_t a = 0xe9, b = 0xd5, c;

    c = a & b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
