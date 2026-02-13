/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int64_t a = 0xc1de171ed89aaeaa, b = 0x39380fd3248dd40f, c;

    c = a | b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
