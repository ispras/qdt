//Arithmetic instruction

#include <stdint.h>

void main(void)
{
    volatile uint32_t a = 0x2b35519e, b = 0x1eb83, c;

    c = a / b;
    c = 0;     //$ch.c

    return;    //$bre
}
