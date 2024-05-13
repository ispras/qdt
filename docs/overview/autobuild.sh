#!/bin/bash

Files=$@

function timestamp() {
 if  [ -f $1 ] ; then
  ls -al --full-time $1
 else
  echo "-"
 fi
}

echo Monitoring $@

Prev=()

for File in $Files
do
    ts=$(timestamp $File)
    # echo $ts
    Prev+=("$ts")
done

echo Timestamps: ${Prev[@]}

while true; do
 sleep 1
 i=0
 changed=0
 Cur=()
 for File in $Files
 do
    ts=$(timestamp $File)
    if ! [ "$ts" = "${Prev[$i]}" ]
    then
        echo Changed "$ts" / "${Prev[$i]}"
        changed=1
    fi
    Cur+=("$ts")
    i=$((i+1))
 done
 Prev=("${Cur[@]}")

 if [ $changed = 1 ]
 then
    make
 fi
done
