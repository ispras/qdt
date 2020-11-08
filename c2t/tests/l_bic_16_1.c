/* Logical instruction */

#include <stdint.h>

int main(void)
{
    volatile int16_t a = 0xedcb, b = 0x1234, c;

#if __MSP430__ == 1
    asm volatile (
        "mov %[srcb], %[dst] \n\
         bic %[srca], %[dst]"
        : [dst] "=rm" (c)
        : [srca] "rm" (a),
          [srcb] "rm" (b)
    );
#else
    c = ~a & b;
#endif
    c = 0;  //$ch.c

    return 0;   //$bre
}
