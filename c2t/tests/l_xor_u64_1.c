/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint64_t a = 0x8439d966de589b65, b = 0x358351e361863bbc, c;

    c = a ^ b;
    FLUSH_PIPELINE;
    c = 0;     //$ch.c

    return;    //$bre
}
