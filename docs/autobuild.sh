#!/bin/bash

File=$1

echo Monitoring $File

Prev=$(ls -al $File)
while true; do
 sleep 1
 Cur=$(ls -al $File)
 if ! [ "$Prev" = "$Cur" ]; then
  echo Changed
  Prev=$Cur
  make
 fi
done
