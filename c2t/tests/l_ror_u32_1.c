/* Logical instruction */

#include <stdint.h>

uint32_t rotr32 (uint32_t a, uint32_t b) {
    return (a >> b) | (a << (((sizeof a) << 3) - b));
}

void main(void)
{
    volatile uint32_t a = 0xa0f585f, b = 0xc, c;

    c = rotr32(a, b);
    c = 0;      //$ch.c

    return;    //$bre
}
