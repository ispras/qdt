---
title: |
  Qemu models development automation toolkit features
author:
- Efimov Vasily (real@ispras.ru)
tags: []
abstract: |
...

# Qemu Development Toolkit (QDT) key features

- Boilerplate code generation

	+ Qemu target CPU architecture
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

+ CPU features (endianness, registers, address length, ...)
+ Instructions encoding
+ Disassembly format

## Output

+ Instruction decoder (a giant `switch` tree)
+ Boilerplate for TCG IR generating functions
+ Disassembler (a giant `switch` tree with prints)
+ CPU device model
+ Infrastructure patches
+ Build system patches

# Full target CPU architecture generation

## Input

+ *same as for partial target CPU architecture generation*
+ Instructions semantic, two variants...

	- I3S code (Instruction Set Semantics Specification),
	  *a C language subset with extra operators to cover TCG IR features.*

	- A Python code (part of input) that generates I3S code using QDT's
	  internal C language model.

## Output

+ *same as for partial target CPU architecture generation*
+ full or partial TCG front-end
  *(depending on the input semantic completeness)*

## Notes

+ I3S code generator distinguish TCG translation time and runtime.
  Some code is left "as is" and some is translated to TCG IR generating
  TCG API calls.

# CPU benchmarking

C2T (CPU Testing Tool)

## Approach

+ Comparison with an oracle.
+ Comparison unit is a simplified feature targeting C program,
  *for instance*...

	- ALU operations.
	- Branching.
	- Procedure call (stack usage).

## Comparison workflow

1. Compile test C program for both target and oracle.
2. Run both binaries under debug.
3. Compare execution logs in terms of C language (variable values,
   line numbers) on breakpoints set by the test author.

The oracles is (frequently) host CPU.
Architecture differences does not matter too much because comparison is on C
language level.

## Notes

- Complex, system level and domain specific instructions can be tested
  using `asm` injection with emulation code provided in C (for the oracle).
  Using C preprocessor condition directives is implied.

- The tool can be configured to compare with a hardware oracle.
  It's only required to provide GDB RSP server.
  GDB RSP client and DWARF interpreter are included.

# Common device boilerplate generation features

## Input

+ Set of Qemu features (Block/Character driver, timer, ...) to be used.
+ Optional register bank description (MMIO / PMIO / PCI(e) BAR)

	- Read-only registers
	- Write-once registers
	- Write-after-read registers
	- RAM-like registers (memory buffers)
	- Virtual registers (no persistent content, specific access handling)

+ Extra QOM properties (device configuration by CLI/VM)
+ Extra internal state (C language `struct`s)

## Output boilerplate includes...

+ Live cycle callbacks and `struct`ures
+ Block driver usage (for ROM images)
+ Character driver usage (for UARTs)
+ Timer callbacks (periodic/delayed events in device)
+ Input IRQ handlers
+ Register bank access callbacks
+ QOM properties
+ VM state description (VMSD) for snapshots
+ Build system and infrastructure patches

# Device type specific boilerplate generation extra features

## System bus device boilerplate generation features

+ Output IRQ
+ MMIO and PMIO register banks

## PCIe bus function boilerplate generation features

+ Vendor ID, Device ID and other ID data
+ INTx IRQ declaration
+ MSI declaration
+ BARs (register banks)
+ Network interface usage

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
  Depending on the input completeness the result code may be a ready VM.

+ QDT provides a GUI with machine diagram view.

# VM diagram view

![MSP430x2xx device diagram](msp430x2xx.png)

# Workflow

![QDT automated workflow](workflow-en.png)

# Example

## Target Architecture (CPU)

**Input**: 3 files, 3039 lines

**Output**: 26 files changed, 19711 insertions

```
 disas/msp430.c                             |  3715 ++++++++
 hw/msp430-all/msp430_hwm.c                 |   364 +
 hw/msp430/msp430_test.c                    |    64 +
 include/disas/dis-asm.h                    |     2 +
 include/exec/poison.h                      |     2 +
 include/hw/msp430-all/msp430_hwm.h         |    38 +
 include/sysemu/arch_init.h                 |     1 +
 softmmu/arch_init.c                        |     2 +
 target/msp430/cpu-param.h                  |    10 +
 target/msp430/cpu.c                        |   147 +
 target/msp430/cpu.h                        |    65 +
 target/msp430/helper.c                     |    43 +
 target/msp430/helper.h                     |     2 +
 target/msp430/machine.c                    |    17 +
 target/msp430/translate.c                  |  2885 +++++++
 target/msp430/translate.inc.c              | 12330 +++++++++++++++++++++++++++
```

## Virtual machine and device boilerplates

**Input**: 1 file, 1104 lines

**Output**: 36 files changed, 4812 insertions

# Questions

https://github.com/ispras/qdt

![QDT link QRC](qdt-qrc.gif)
