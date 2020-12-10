.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

setn
setc
rra r2
br_1:

.include "tools/pop_regs.s"

ret
