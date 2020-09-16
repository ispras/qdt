__all__ = [
    "BYTE_BITSIZE"
  , "OPERAND_MAX_BITSIZE"
  , "SUPPORTED_READ_BITSIZES"
]


# Note, for code readability only
BYTE_BITSIZE = 8

OPERAND_MAX_BITSIZE = 64

# Note, descending order is needed to correctly calculate the size of readings
SUPPORTED_READ_BITSIZES = (64, 32, 16, 8)
