//Control flow instruction

#include <stdint.h>

void main(void)
{
    volatile uint64_t a = 0x22a7a5c8e1209c9f, b = 0xb1d279a21a8a7c48, c = 0;

    if (a == b) {
        c = 1;  //$br
    } else {
        c = -1; //$br
    }

    return;     //$bre
}
