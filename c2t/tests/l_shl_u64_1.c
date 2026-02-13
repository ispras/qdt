/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint64_t a = 0xd65237f3761b20d, b = 0x25, c;

    c = a << b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
