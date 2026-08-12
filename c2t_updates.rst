Updates for C2T
===============

.. workflow:: MR
   :tags: MR, bug, feature
   :branch: c2t_updates
   :assignee: bda

First, there are some bug fixes to C2T and related items of ``debug`` module.

A work has made on error reporting.

Test set is significantly changed...

* Naming became more informative.

* Tests for `float`/`double` have been added.
  Those tests have not been wrote correctly initially.
  So, there is a non-squased history of them.

* A support of software pipeline CPU is added.
  The thing is frequently associated with VLIW processors.
  On a software pipeline an instruction may run multiple cycles while
  the pipeline is continuously fed with consequent instructions.
  So, several instruction are run simultaneously.
  And the result of an instruction is not yet available to the next
  instruction in code flow, but it is available in some number of clocks.
  Hence a break point set on next instruction sees incorrect result.
  The ``FLUSH_PIPELINE`` macro is injected.
  It's empty for regular CPUs.
  The commit series defines it as ``nop`` for x86_64.
  But it is for example only, not required actually.
  A test config for a software pipeline CPU may define it using ``-D``,
  macro pre-definition option.
  For instance, ``-DFLUSH_PIPELINE='asm("nop 13")'`` with big enough
  number ensures that all instructions on the CPU finished and
  memory (variable values) is ready to be checked by C2T.

``common.stdfilter`` is added.
It is used to add line prefixes to output of all C2T processes.

``misc/linetab.py`` script rearranges that output of C2T in a table.
One column for each process (line prefix).
It's usable in C2T log analysis.
