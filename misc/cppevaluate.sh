#!/bin/bash

export PYTHONPATH="..:$PYTHONPATH"

QEMU_SRC="$HOME/work/qemu/src"
QEMU_BUILD="$HOME/work/qemu/debug/build"

CPPTEST_ARGS=" \
	$QEMU_SRC \
	-t 3600 \
	-I$QEMU_BUILD \
	-I$QEMU_BUILD/slirp/src \
	-I$QEMU_SRC \
	-I$QEMU_SRC/accel/tcg \
	-I$QEMU_SRC/capstone/include \
	-I$QEMU_SRC/dtc/libfdt \
	-I$QEMU_SRC/include \
	-I$QEMU_SRC/net \
	-I$QEMU_SRC/slirp/src \
	-I$QEMU_SRC/target/i386 \
	-I$QEMU_SRC/tcg/i386 \
	-I/usr/include/at-spi-2.0 \
	-I/usr/include/at-spi2-atk/2.0 \
	-I/usr/include/atk-1.0 \
	-I/usr/include/cairo \
	-I/usr/include/dbus-1.0 \
	-I/usr/include/freetype2 \
	-I/usr/include/gdk-pixbuf-2.0 \
	-I/usr/include/gio-unix-2.0 \
	-I/usr/include/gio-unix-2.0 \
	-I/usr/include/glib-2.0 \
	-I/usr/include/gtk-3.0 \
	-I/usr/include/harfbuzz \
	-I/usr/include/libpng16 \
	-I/usr/include/libusb-1.0 \
	-I/usr/include/libxml2 \
	-I/usr/include/p11-kit-1 \
	-I/usr/include/pango-1.0 \
	-I/usr/include/pixman-1 \
	-I/usr/include/vte-2.91 \
	-I/usr/lib/x86_64-linux-gnu/dbus-1.0/include \
	-I/usr/lib/x86_64-linux-gnu/glib-2.0/include \
"

$(cd ../ply && git checkout base)

if ! python cpptest.py $CPPTEST_ARGS ; then exit 1 ; fi

$(cd ../ply && git checkout refactor)

if ! python cpptest.py $CPPTEST_ARGS ; then exit 1 ; fi

$(cd ../ply && git checkout inc_cache)

if ! python cpptest.py $CPPTEST_ARGS ; then exit 1 ; fi

$(cd ../ply && git checkout incd_cache)

if ! python cpptest.py $CPPTEST_ARGS ; then exit 1 ; fi
