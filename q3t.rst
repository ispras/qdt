Qemu Target Testing Tool (Q3T)
==============================

.. workflow:: MR
   :tags: MR, feature
   :branch: q3t
   :assignee: bda

This commit series introduces a new testing method implementation.
The method is to write tests in any way a target toolchain supports.
Then test are to be compiled to binaries.
Q3T launches a binary in Qemu to be tested, under debug through GDB RSP stub.
It checks runtime values using the way described below.

The way those binaries are got is out of Q3T's scope.
A target toolchain must return binaries in Q3T supported formats.
ELF is only supported now.
Those binaries must contain a debug info in Q3T supported formats.
DWARF v4 is only supported.
However, v3 and v5 is known to be compatible too, in some cases.
Q3T reads source code of binaries.
So, the source code is to be available during the operation.

Global (exported) symbols with special names are to be added
to the source code.
I.e. labels in assembly or functions in C (labels in C are not exported).
Those symbols are break points.
The prefix is required to distinguish break points of interest and
regular symbols.
The symbol prefix is configurable.
A break point is to be accompanied with Python expressions
with a special prefix.
Expressions is likely to be wrapped in language specific comment syntax.
The prefix is required to distinguish expressions and regular comments.
Also, Q3T can't know all comment syntax.
So, the prefix is a hint for it.
The expression prefix is configurable.
There is an operation mode in which only expressions are required.
This is especially useful versus an optimizing C compiler dropping functions
with empty bodies.

Python expressions must return a value ``bool``ling to ``True``.
Q3T defines an environment which allows access to

* target registers,
* target memory,
* debug symbols,
* python builtin functions,
* etc.

There are few helpers to write low level checks.
E.g.,

* signed/unsigned integer interpretation,
* float-point numbers interpretation,
* little-/big-endian multibyte integers conversions,
* etc.

A Python script instantiating ``Q3T`` configuration is required.
E.g., ``q3t.py``.
It must define...

* ``rsp``, ``QRSP`` target, a definition of target for GDB RSP protocol.
* ``args``, an iterable, a command to launch Qemu.
   ``{variables}`` are available for CLI argument definition.
   E.g., ``["-kernel", "{bin}"]`` can take a part in the ``args`` sequence.
* ``bins``, an iterable, binary files of tests.
   E.g., ``(f for f in listdir(dirname(__file__)) if f.endswith(".elf"))``
   generator ``yield``s all ``*.elf`` files in the same directory with the
   configuration script (``q3t.py``).

The patch series first extends existing QDT capabilities.
``debug`` package is touched mostly.
New features are added. 
DWARF information analysis is extended.
Some patches are not squashed for history, but they are placed tightly.

Then a big sub-series of patches adds Q3T.
Those patches are to be considered a single patch.
They are not squashed for history.
Final diff to be reviewed.
