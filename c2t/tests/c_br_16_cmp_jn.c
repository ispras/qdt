/* Control flow instruction */

#include "common.h"

int main(void)
{
    volatile int16_t a = 0x1234, b = 0x123, c;
#if __MSP430__ == 1
    asm volatile goto (
        "cmp %[src_a], %[dst_b] \n\
         jn %l[label]"
        :
        : [dst_b] "rm" (b),
          [src_a] "rm" (a)
        : "cc"
        : label
    );
#else
    if (b - a < 0) {
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
