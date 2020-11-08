/* Control flow instruction */

#include <stdint.h>

volatile int16_t a[4] = {1, 2, 3, 0};

void main(void)
{
    volatile int16_t c;
    volatile int16_t *pa = a;

#if __MSP430__ == 1
    asm volatile (
        "loop_start: cmp #0, @%[src] \n\
        jz loop_end \n\
        add @%[src]+, %[dst] \n\
        jmp loop_start \n\
        loop_end:"
        : [dst] "=&r" (c)
        : [src] "r" (pa)
        : "cc"
    );
#else
loop_start:
    if (*pa == 0) {
        goto loop_end;
    }
    c += *(pa++);
    goto loop_start;
loop_end:
#endif
    c = 0; //$ch.c

    return;    //$bre
}

