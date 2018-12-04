//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint64_t a = 0x16c3780415d06cba, b = 0x300724b6f36e801, c;

    c = a + b;
    c = 0;     //$ch.c

    return;    //$bre
}
