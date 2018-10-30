#!/bin/bash

File=$1

function timestamp() {
 ls -al --full-time $1
}

echo Monitoring $File

Prev=$(timestamp $File)
while true; do
 sleep 1
 Cur=$(timestamp $File)
 if ! [ "$Prev" = "$Cur" ]; then
  echo Changed
  Prev=$Cur
  make
 fi
done
