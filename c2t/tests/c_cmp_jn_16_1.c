/* Control flow instruction */

#include <stdint.h>

int main(void)
{
    volatile int16_t a = 0x1234, b = 0x123, c;
#if __MSP430__ == 1
    asm volatile goto (
        "cmp %[src], %[dst] \n\
         jn %l[label]"
        :
        : [dst] "rm" (b),
          [src] "rm" (a)
        : "cc"
        : label
    );
#else
    if (b - a < 0) {
        goto label;
    }
#endif
    c = a;  //$br
label:
    c = b;  //$br

    return 0;   //$bre
}
