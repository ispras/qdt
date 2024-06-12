CFLAGS+=-g -O0 -no-pie

progs:=main

debug: main.exe
	gdb -iex "set auto-load safe-path /" main.exe
