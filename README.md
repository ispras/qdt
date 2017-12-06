# QEMU Development Toolkit

The goal of this project is to automate device and machine development for
QEMU.

*Capabilities*:

- A device stub generator.
- A graphical editor representing a machine schematically.
It able to generate a machine draft.
- A common graphical user interface integrating both device and machine
generators.

*Current implementation limitations*:

- The device stub generator supports system bus and PCI(E) bus device
generation only.
- The machine draft generator does not generate CLI argument accounting.
A developer have to implement it manually if required.
- A CPU instantiation is also too specific and not fully supported.
Therefore, a developer have to handle it after generation.
- Old-style device models which are normally instantiated in specific way, are
not supported by machine graphical editor.
But a developer still can use device stub generator to update implementation
of such devices.
After that, those devices do become supported by the editor.

### Device stub generation overview

A device model in QEMU is a module and a header in C language whose implements
the behavior and other specifics of the device.
The implementation uses the API provided by the QEMU infrastructure.
Usage of elements of the API is quite similar from one device to another.
The generator utilizes this feature to generate both a header and a module
for the device with API stubs.
Amount of generated lines is 11-25 times more than the size of generation
parameters.
The GUI does simplify the setting of those parameters.

Generated device stubs are registered in QEMU build system and ready to
compile.
A developer may immediately concentrate on the device specifics implementation.

### Machine draft generation overview

A machine model in QEMU is a module in C language.
The main part of a machine module is the machine initialization function.
The function is a sequence of device, bus, IRQ and memory instantiations.
QEMU provides common API to instantiate and interconnect those machine nodes.
Of course there is some auxilary code in the module.
The toolset uses an object model describing the content of a machine.
Each class of this model describes corresponding machine node.
There is a graphical editor which provides a schematic visualization of
machine content.
The editor is paired with a generator producing a module draft for the machine
represented in the editor.

A generated machine draft contains most of the machine code.
It includes the initialization function and most of the auxilary code.
The draft is also registered in QEMU build system and ready to build.

