/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint8_t a = 0x7e, c;

    c = ~a;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
