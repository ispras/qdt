/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0x7c36, c;

    c = ~a;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
