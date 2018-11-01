#!/usr/bin/python2
# -*- coding: utf-8 -*-

# translates UTF-8 characters in TeX commands to A-Z
# Ex.:
# In: \newcommand{\пример}{example} % Cyrillic
# Out: \newcommand{\AEDPAEEAAEDIAEDMAEDFAEEA}{example} % Cyrillic

from sys import (
    stdin,
    stdout
)

SLASH = ord("\\")
COMMAND_TERM = tuple(ord(c) for c in " {\n\\")
A = ord("A")

def tocommand(i):
    ret = chr((i & 0b1111) + A)
    while i:
        i = i >> 4
        ret = chr((i & 0b1111) + A) + ret
    return ret

# states of translator, a deterministic finite automaton

def noncommand(b):
    global state
    "Not inside a TeX command"
    if b == SLASH:
        state = nonutf8
    return chr(b)

def nonutf8(b):
    "Not inside UTF-8 character"
    global state
    if not b & 0b10000000:
        if b in COMMAND_TERM:
            state = noncommand
        return chr(b)
    global code
    if b & 0b11100000 == 0b11000000:
        state = utf8_2_2
        code = b & 0b00011111
        ret = b""
    elif b & 0b11110000 == 0b11100000:
        state = utf8_3_2
        code = b & 0b00001111
        ret = b""
    elif b & 0b11111000 == 0b11110000:
        state = utf8_4_2
        code = b & 0b00000111
        ret = b""
    else:
        ret = chr(b)
    return ret

def utf8_2_2(b):
    "2nd byte of 2 byte UTF-8"

    global state
    global code
    if b & 0b11000000 != 0b10000000:
        # recover previous byte
        ret =  chr(code | 0b11000000) + chr(b)
    else:
        code = (code << 6) | b & 0b00111111
        ret = tocommand(code)
    state = nonutf8
    return ret

def utf8_3_2(b):
    "2nd byte of 3 byte UTF-8 character"
    raise NotImplementedError()

def utf8_4_2(b):
    "2nd byte of 4 byte UTF-8 character"
    raise NotImplementedError()

state = noncommand

if __name__ == "__main__":
    for l in stdin:
        for b in l:
            stdout.write(state(ord(b)))

