---
title: |
  Qemu models development automation toolkit features
author:
- Efimov Vasily (real@ispras.ru)
tags: []
abstract: |
...

# Qemu models development automation toolkit

Qemu Development Toolkit (QDT)

https://github.com/ispras/qdt

![QDT link QRC](qdt-qrc.gif)

# Key features

- Boilerplate code generation

	+ Qemu target CPU architecture (with CPU device)
	+ System/PCI(e) bus device
	+ Virtual Machine

- Functional code generation

	+ Target instruction decoder and semantic (TCG frontend)
	+ Target code disassembler
	+ GDB RSP target specifics (debug server)
	+ Build system integration

- Debugging

	+ CPU benchmarking over set of feature targeting C programs

- Python API, inputs are Python scripts

# Partial target CPU architecture generation

## Input

+ Top level CPU features (endianess, registers, name, ...)
+ Instructions decoding
+ Instructions disassembly format

## Output

+ Instruction decoder (a giant `switch` tree)
+ Boilerplate for TCG IR generating functions
+ Disassembler (a giant `switch` tree with prints)
+ CPU device model
+ Build system and infrastructure patches

# Full target CPU architecture generation

## Input

+ *same as for partial target CPU architecture generation*
+ Instructions semantic, two variants...

	- I3S code (Instruction Set Semantics Specification),
	  *a C language subset with extra operators to cover TCG capabilities.*

	- A Python code (part of input) that generates I3S code using QDT's
	  internal C language model.

## Output

+ *same as for partial target CPU architecture generation*
+ full or partial TCG front-end
  *(depending on the input semantic completeness)*

## Notes

+ I3S code generator distinguish TCG translation and run time.
  Some code is left "as is" and some is translated to TCG IR generating
  TCG API calls.

# CPU benchmarking

The tool: C2T (CPU Testing Tool)

## Approach

+ Comparison with an oracle.
+ Comparison unit is a simple feature targeting C program, ex...

	- Arithmetic operation.
	- Branching.
	- Procedure call (stack using).

## Comparison workflow

1. Compile test C program for both target and oracle.
2. Run both binaries under debug.
3. Compare execution logs in terms of C language (variable values,
   line numbers) on breakpoints set by the test author.

The oracles is (frequently) host CPU.
Architecture differences does not mater too much because comparison is on C
language level.

## Notes

- Complex, system level and domain specific instructions can by tested
  using `asm` injection with provided emulation in C for oracle
  architecture using C preprocessor condition directives.

- The tool can be configured to compare with a hardware oracle.
  It's only required to provide GDB RSP server.
  GDB RSP client and DWARF interpreter are included.

# Common device boilerplate generation features

## Input

+ Required Qemu features (Block/Character driver, timer, ...)
+ Register bank description (MMIO / PMIO / PCI(e) BAR)

	- Read-write registers
	- Read-only registers
	- Write once registers
	- Write after read registers
	- RAM-like registers (big buffers)
	- Virtual registers (no persistent content, specific access handling)
	- Gaps

+ User properties (device configuration by CLI/VM)
+ Extra internal state (C language `struct`s)

## Output boilerplate includes...

+ Live cycle callbacks and key structures
+ Block driver usage (for ROM images)
+ Character driver usage (for UARTs)
+ Timer callbacks (periodic/delayed events in device)
+ Input IRQ handlers
+ Register bank access callbacks
+ QOM properties
+ VM state description (VMSD) for snapshots
+ Build system and infrastructure patches

# System bus device boilerplate generation features

+ Output IRQ
+ MMIO and PMIO register banks

# PCIe bus function boilerplate generation features

+ Vendor ID, Device ID and other ID data
+ INTx IRQ declaration
+ MSI declaration
+ BARs (register banks)

# Virtual machine boilerplate generation features

## Input

+ Devices and instantiation parameters...

	- Model name
	- QOM properties values
	- MMIO/PMIO register banks base addresses

+ Buses
+ Device interconnections...

	- IRQ lines (source/destination device)
	- Bus-device hierarchy

+ Memory map...

	- RAMs/ROMs
	- Aliases

## Output

+ Live cycle callbacks and key structures

## Notes

+ Most of a virtual machine "body" is in `init` life cycle callback.
  Depending on the input completeness the result code may be ready to run.

+ QDT provides a GUI with machine diagram view.

![MSP430x2xx device diagram](msp430x2xx.png)


