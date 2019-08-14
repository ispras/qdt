  The implementation of the new virtual processor architecture in Qemu involves
  the creation of a dynamic binary translator TCG front-end for this
  processor architecture.
  Testing is necessary to verify the correctness of the implementation of this
  translator component.
  Currently, the TCG front-end testing systems use an approach based on a
  comparison with an oracle.
  This oracle have the same processor architecture.
  And the oracle may be a real processor, a virtual machine with high emulation
  accuracy, or another binary translator.
  Unfortunately, such oracles are not always available.
  This paper is devoted to testing the processor architecture implementation
  in Qemu with the lack of the necessary oracle for comparison.
  The main idea is that a program written in a high-level programming language
  should execute equally regardless of processor architecture.
  In other words, one can use a processor with a different architecture for
  comparison.
  In this paper, this is the processor of a developer machine.
  In fact, the oracle architecture — AMD64.
  The objects of comparison of this approach are the essence of a high-level
  programming language.
  Tests are written in this language.
  The C language ​​was chosen for this purpose, because, on the one hand, it is
  fairly close to the hardware, and on the other, it has good portability.
  The approach is implemented in the c2t tool (Processor Testing Tool) and is
  part of QDT [[$](# ref.QDT)].
  Source code is available here: https://github.com/ispras/qdt.
  C2t is implemented in the Python programming language and supports testing
  of Qemu in full system and user level emulation modes.
  This tool is suitable for testing TCG front-ends obtained using the TCG
  front-end automation generating system [[$](# ref.TCGgen)], and implemented
  in the classical way (manually).
