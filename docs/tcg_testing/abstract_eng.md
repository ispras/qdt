  Implementing a new target architecture in Qemu involves creation of a
  dynamic binary translator TCG front-end for that architecture.
  Testing is necessary to verify correctness of that translator component.
  Currently, existing TCG front-end testing systems use an approach based on a
  comparison with an oracle.
  Such oracle have the same processor architecture.
  And an oracle may be a real processor, a high-fidelity emulator or another
  binary translator.
  Unfortunately, such oracles are not always available.
  This paper is devoted to testing a target architecture implementation
  in Qemu <!-- with the lack of the necessary oracle for comparison.-->
  when the necessary oracle is not available.
  The main idea is following.
  There is observation, a program written in a high-level programming language
  is expected to execute equally regardless of processor architecture.
  In other words, one can use a real processor with a different architecture
  for comparison.
  In this paper, it is the processor of a developer machine.
  In fact, the oracle architecture is AMD64.
  The comparison objects are the term <!--entities--> of a high-level
  programming language.
  I.e. tests are written in C.
  C language ​​was chosen for this purpose, because, on the one hand, it is
  fairly close to the hardware, and, on the other, it has good portability.
  The approach is implemented in CPU Testing Tool (c2t) which is
  part of QDT [[$](# ref.QDT)].
  Source code is available at https://github.com/ispras/qdt.
  The tool is implemented in Python programming language and supports
  testing of Qemu in both full system and user level emulation modes.
  c2t is suitable for testing TCG front-ends which are <!--either--> generated
  by the
  automatic TCG front-end generation system [[$](# ref.TCGgen)] or implemented
  in the classical way (manually).
