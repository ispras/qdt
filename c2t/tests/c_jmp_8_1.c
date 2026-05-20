/* Control flow instruction */

#include "common.h"

int main(void)
{
    volatile int8_t a = 0xa, b = 0xb, c;
#if __MSP430__ == 1
    asm volatile goto (
        "jmp %l[label]"
        :
        : 
        :
        : label
    );
#else
    if (a) {
        goto label;
    }
#endif

    FLUSH_PIPELINE;

    c = a;  //$br

    FLUSH_PIPELINE;

label:

    FLUSH_PIPELINE;

    c = b;  //$br

    FLUSH_PIPELINE;

    return 0;   //$bre
}
