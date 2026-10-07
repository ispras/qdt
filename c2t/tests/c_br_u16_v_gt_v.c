/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile uint16_t a = 0xe9db, b = 0x3312, c = 0;

    if (a > b) {
        FLUSH_PIPELINE;

        c = 1;  //$br

        FLUSH_PIPELINE;
    } else {
        FLUSH_PIPELINE;

        c = -1; //$br

        FLUSH_PIPELINE;
    }

    FLUSH_PIPELINE;

    return;     //$bre
}
