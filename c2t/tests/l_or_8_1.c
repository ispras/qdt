/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int8_t a = 0xcb, b = 0xe7, c;

    c = a | b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
