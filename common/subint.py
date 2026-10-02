"""

1 ~ 1.? ~ NaN
. is always before MSb
10 ~ 1.0
11 ~ 1.1

100 ~ 1.00 == 1.0 ~ 10
101 ~ 1.01
110 ~ 1.10 == 1.1 ~ 11
111 ~ 1.11

1000 ~ 1.000 == 1.00 ~ 100 == 1.0 ~ 10
1001 ~ 1.001
1010 ~ 1.010 == 1.01 ~ 101
1011 ~ 1.011
1100 ~ 1.100 == 1.10 ~ 110 == 1.1 ~ 11
1101 ~ 1.101
1110 ~ 1.110 == 1.11 ~ 111
1111 ~ 1.111

101 = (11 << 1) - 1
111 = (11 << 1) + 1

(101 << 1) - 1 == 1001
(101 << 1) + 1 == 1011

"""

_int_lt = int.__lt__

class subint(int):

    def above(self):
        # return subint((int(self) << 1) + 1)
        return subint((self << 1) + 1)

    def below(self):
        # return subint((int(self) << 1) - 1)
        return subint((self << 1) - 1)

    def __lt__(self, o):
        if not isinstance(o, subint):
            return NotImplemented
        sbl = self.bit_length()
        obl = o.bit_length()
        if sbl < obl:
            d = obl - sbl
            com = o >> d  # common MSb(its).
            if _int_lt(self, com):
                return True
            if com < self:
                return False
            # self == com
            lsbm = (1 << d) - 1  # LSb mask
            return bool(o & lsbm)
        if obl < sbl:
            d = sbl - obl
            com = self >> d
            if com < o:
                return True
            # if _int_lt(o, com):
            #     return False
            # o == com
            # self == o or o < self
            return False
        return _int_lt(self, o)

    def __str__(self):
        i = int(self)
        ret = ""
        while 1 < i:
            ret = ("1" if i & 1 else "0") + ret
            i >>= 1
        return "1." + ret


if __name__ == "__main__":
    from bisect import (
        insort,
    )

    a = [subint(0b11)]

    for _ in range(5):
        for i in tuple(a):
            u = i.above()
            if u not in a:
                insort(a, u)
            d = i.below()
            if d not in a:
                insort(a, d)

    prev_f = 0.0
    prev_s = "0.0"
    for i in a:
        s = str(i)
        f = float(s)
        print("%-20s : %-19s" % (s, bin(int(i))[2:]))
        assert prev_f <= f
        assert prev_s <= s
        prev_f = f
        prev_s = s
