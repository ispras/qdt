__all__ = [
    "BYTE_SIZE"
  , "OPERAND_MAX_SIZE"
  , "SUPPORTED_READ_SIZES"
]


# sizes in bits
# XXX: do we support arbitrary byte size or this is for code readability only?
BYTE_SIZE = 8
OPERAND_MAX_SIZE = 64
# XXX: as a constant it should be a tuple
SUPPORTED_READ_SIZES = [8, 16, 32, 64]
