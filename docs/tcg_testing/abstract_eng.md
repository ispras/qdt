---
title: |
  Automated testing of a TCG frontend for Qemu
author:
- Koltunov D.S. &lt;koltunov@ispras.ru>
- Efimov V.Y. &lt;real@ispras.ru>
tags: []
abstract: |
  <br>

  **Abstract.**

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

  **Keywords**:
  Qemu;
  automated testing of a TCG frontend;
  QDT;
  GDB RSP
...

# References

[$]. <a name="ref.QDT_eng"></a>Efimov V.Yu., Bezzubikov A.A., Bogomolov D.A.,
Goremykin O.V., Padaryan V.A. Automation of device and machine development for
QEMU. Trudy ISP RAN/Proc. ISP RAS, vol. 29, issue 6, 2017, pp. 77-104
(In Russian). DOI: 10.15514/ISPRAS-2017-29(6)-4

[$]. <a name="ref.TCGgen_eng"></a>Bezzubikov A., Belov N., Batuzov K. Automatic
dynamic binary translator generation from instruction set description // 2017
Ivannikov ISPRAS Open Conference (ISPRAS). — Vol. 1. — United States: United
States, 2017.

[$]. <a name="ref.oracle_testing_eng"></a>W. E. Howden, "Theoretical and
empirical studies of program testing", Proc. 3rd Int. Conf. Software
Engineering, pp. 305-311, 1978.

[$]. <a name="ref.EmuFuzzer_eng"></a>Lorenzo Martignoni, Roberto Paleari,
Giampaolo Fresi Roglia, Danilo Bruschi, Testing CPU emulators, Proceedings of
the eighteenth international symposium on Software testing and analysis, July
19-23, 2009, Chicago, IL, USA.

[$]. <a name="ref.KEmuFuzzer_eng"></a>Lorenzo Martignoni, Roberto Paleari,
Giampaolo Fresi Roglia, Danilo Bruschi, Testing system virtual machines,
Proceedings of the 19th international symposium on Software testing and
analysis, July 12-16, 2010, Trento, Italy.

[$]. <a name="ref.hi_4_lo_eng"></a>L. Martignoni, S. McCamant, P. Poosankam,
D. Song, and P. Maniatis, "Path-exploration lifting: Hi-fi tests for lo-fi
emulators," in Proc. of the International Conference on Architectural Support
for Programming Languages and Operating Systems, London, UK, Mar. 2012.

[$]. <a name="ref.pill_testing_eng"></a>Hao Shi, Abdulla Alwabel, and Jelena
Mirkovic. 2014. Cardinal pill testing of system virtual machines. In
Proceedings of the 23rd USENIX Security Symposium (USENIX Security’14).
271-285.

[$]. <a name="ref.RISU"></a>Risu: random instruction sequence tester for
userspace. Available at:
https://git.linaro.org/people/pmaydell/risu.git/about/, accessed: 09.08.2019.

[$]. <a name="ref.PokeEMU"></a>Qiuchen Yan and Stephen McCamant. 2018. Fast
PokeEMU: Scaling
Generated Instruction Tests Using Aggregation and State Chaining.
In VEE ’18: 14th ACM SIGPLAN/SIGOPS International Conference on
Virtual Execution Environments, March 25, 2018, Williamsburg, VA,
USA. ACM, New York, NY, USA, 13 pages.

[$]. <a name="ref.MeanDiff"></a>Soomin Kim, Markus Faerevaag, Minkyu Jung,
SeungIl Jung, DongYeop Oh, JongHyup Lee, Sang Kil Cha, Testing intermediate
representations for binary analysis, Proceedings of the 32nd IEEE/ACM
International Conference on Automated Software Engineering, October 30-November
03, 2017, Urbana-Champaign, IL, USA.

[$]. <a name="ref.MicroTESK"></a>Камкин А.С., Сергеева Т.И., Смолов С.А.,
Татарников А.Д., Чупилко М.М. Расширяемая среда генерации тестовых программ
для микропроцессоров. Программирование, № 1, 2014, стр. 3-14.

[$]. <a name="ref.arm_isa"></a>ARM and Thumb-2 Instruction Set Quick Reference
Card. Available at:
http://infocenter.arm.com/help/topic/com.arm.doc.qrc0001m/QRC0001_UAL.pdf,
accessed: 16.07.2019.

[$]. <a name="ref.mips_isa"></a>MIPS Instruction Reference. Available at:
https://s3-eu-west-1.amazonaws.com/downloads-mips/documents/MD00565-2B-MIPS32-Q
RC-01.01.pdf, accessed: 16.07.2019.

[$]. <a name="ref.msp430_isa"></a>MSP430x2xx Family User's Guide.
Available at: http://www.ti.com/lit/ug/slau144j/slau144j.pdf, accessed:
16.07.2019.

[$]. <a name="ref.pyrsp"></a>pyrsp. Available at:
https://github.com/stef/pyrsp, accessed: 02.08.2019.

[$]. <a name="ref.pyelftools"></a>pyelftools. Available at:
https://github.com/eliben/pyelftools, accessed:23.09.2018.
