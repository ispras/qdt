/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0xe9db, b = 0x3312, c = 0;

    if (a == b) {
        c = 1;  //$br
    } else {
        c = -1; //$br
    }

    return;     //$bre
}
