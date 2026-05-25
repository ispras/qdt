/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile int64_t a = 0x60764141227e76f4, b = 0xfdf97a16478efb89, c;

    c = a & b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
