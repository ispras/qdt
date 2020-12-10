.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

push #0
push #0
push #0
push #0
push #0
push #0
add #12, r1
push.b #-1
push.b #0
push.b #1
push.b #2
push.b #4
push.b #8
br_1:

.include "tools/pop_regs.s"

ret
