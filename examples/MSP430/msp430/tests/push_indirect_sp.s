.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

push #0x1234
push #0xfeed
pop r5
push @r1
br_1:

.include "tools/pop_regs.s"

ret
