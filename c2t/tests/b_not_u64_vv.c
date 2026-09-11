/* Logical instruction */

#include "common.h"

void main(void)
{
    volatile uint64_t a = 0xbd48c93046c566d5, c;

    c = ~a;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
