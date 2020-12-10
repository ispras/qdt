.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

.p2alignw 11, 0x4303

mov #0x300, r1
mov #0xfeed, 0x32f8(r0)
br_1:

.include "tools/pop_regs.s"

ret
