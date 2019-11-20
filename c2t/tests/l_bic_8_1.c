/* Logical instruction */

#include <stdint.h>

int main(void)
{
    volatile int8_t a = 0x2a, b = 0x5, c;

#if __MSP430__ == 1
    __asm__ volatile ("mov %[srcb], %[dst]\n\t"
                      "bic %[srca], %[dst]"
                      : [dst] "=rm" (c)
                      : [srca] "rm" (a),
                        [srcb] "rm" (b));
#else
    c = ~a & b;
#endif
    c = 0;  //$ch.c

    return 0;   //$bre
}
