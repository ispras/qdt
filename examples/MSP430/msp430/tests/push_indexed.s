.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

push #0xfeed
push #0x1234
push 2(r1)
mov 2(r1), r5
br_1:

.include "tools/pop_regs.s"

ret
