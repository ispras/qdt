.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

mov #0x300, r1
mov #0xfeed, &0x300
br_1:

.include "tools/pop_regs.s"

ret
