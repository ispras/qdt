/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int32_t a = 0xd19ea5fb, b = 0x5430b6c3, c;

    c = a & b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
