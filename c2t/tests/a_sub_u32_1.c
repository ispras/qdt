//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint32_t a = 0x1df473e4, b = 0x58bac230, c;

    c = a - b;
    c = 0;     //$ch.c

    return;    //$bre
}
