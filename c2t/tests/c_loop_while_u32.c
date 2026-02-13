#include "common.h"

void main(void)
{
    volatile uint32_t i;
    register uint32_t c;
    c = 10;
    while (c--) {
        i++; //$ch.i
    }
    return; //$bre
}
