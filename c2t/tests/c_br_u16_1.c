//Control flow instruction

#include <stdint.h>

void main(void)
{
    volatile uint16_t a = 0xe9db, b = 0x3312, c;

    if (a == b) {
        c = 1;  //$ch.c
    } else {
        c = -1; //$ch.c
    }

    return;     //$bre
}
