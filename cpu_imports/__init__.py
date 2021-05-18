__all__ = [
    "MemOp"
]

from source import (
    CINT
  , CSTR

# CPU instructions semantics definition
  , Type
  , Comment
  , Call
  , MCall
  , Macro
  , Function
  , Declare
  , Variable
  , BranchSwitch
  , SwitchCase
  , OpAssign
  , OpIndex
  , OpAdd
  , BranchIf
  , BranchElse
  , OpLess
  , OpOr
  , OpAnd
  , OpNot
  , OpEq
)
from qemu import (
# CPU template generation settings
    CPUInfo
  , CPURegister
  , gen_reg_names_range
  , Instruction
  , Opcode
  , Operand
  , Reserved
# helpers
  , underscored_name_shortener
# heuristic
  , get_vp
)

# Cache some types to shorten the semantics code of instructions.
MemOp = Type[get_vp("memop")]
