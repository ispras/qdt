.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

push #0
push #0
push #0
pop r15
pop r15
pop r15
push #mov_1
push #mov_2
push #br_2
br_1:
add #2, r1

.word 0x1291 ;call 0(r1)
.word 0x0000

mov_1:
mov #0, r4
mov_2:
mov #0, r5
br_2:
mov #0, r6
ret

.include "tools/pop_regs.s"

ret
