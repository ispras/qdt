.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

.p2alignw 11, 0x4303

.rept 121
nop
.endr

mov #0, r12

push #br_2
push #0x4030 ;br

push #0x4304 ;mov #0, r4
push #0x4305 ;mov #0, r5
push #0x4306 ;mov #0, r6

add #2, r1 ;sp on "mov #0, r5"
br_1:
call r1
mov #0, r7
mov #0, r8
br_2:
mov #0, r9
ret

.include "tools/pop_regs.s"

ret
