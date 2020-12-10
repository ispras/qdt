.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

mov #0xBEEF, r10
swpb r10
br_1:

.include "tools/pop_regs.s"

ret
