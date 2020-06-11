# -*- coding: utf-8 -*-

from common import (
    estr
)


raw = b"\xdf\x00" # utf-8 error

raw += u"кириллица".encode("utf-8") + raw + b" lathin"

s = estr(raw)

str(s)
print(s)
print(s[2])
print(s[2:6])
print(repr(s))

new_raw = s.encode("utf-8")

print(repr(raw))
print(repr(new_raw))
assert new_raw == raw
