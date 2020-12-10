#!/bin/bash

for f in $(ls | grep qemu.log | sed -e s/[.]qemu[.]log//);
do
    if [ "" != "$(diff $f.qemu.log $f.hw.log)" ];
    then
        echo "$f differs"
        diff -U 10 $f.qemu.log $f.hw.log > $f.diff;
    fi;
done

