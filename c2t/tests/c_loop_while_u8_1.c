#include "common.h"

void main(void)
{
    volatile uint8_t c, i;
    c = 10;
    while (--c) {
        FLUSH_PIPELINE;
        i++; //$ch.i, ch.c
    }
    return; //$bre
}
