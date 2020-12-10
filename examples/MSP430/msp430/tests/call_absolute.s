.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

call &addr_br
addr_br:
.word br_1
mov #0, r4
mov #0, r5
br_1:
mov #0, r6
ret

.include "tools/pop_regs.s"

ret
