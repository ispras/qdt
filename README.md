# QEMU Development Toolkit

The goal of this project is to automate device and machine development for
QEMU.

*Capabilities*:

- A device stub generator.
- A graphical editor representing a machine schematically.
It outputs a machine draft.
- A common graphical user interface aiding in generation of both a device
and a machine.

*Current implementation limitations*:

- The device stub generator supports system bus and PCI(E) bus device
generation only.
- The machine draft generator does not automate CLI argument accounting in a
machine model.
A developer have to implement it manually if required.
- A CPU instantiation is also too specific and not fully supported.
Therefore, a developer have to handle it after generation.
- Old-style device models which are normally instantiated in specific way, are
not supported by machine graphical editor.
But a developer still can use device stub generator to update implementation
of such devices.
After that, those devices are supported by the editor.

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
A developer may concentrate on the device specifics implementation.

### Machine draft generation overview

A machine model in QEMU is a module in C language.
The main part of a machine module is the machine initialization function.
The function is a sequence of device, bus, IRQ and memory instantiations.
QEMU provides common API to instantiate and interconnect those machine nodes.
Of course there is some auxilary code in the module.
The toolset uses an object model describing the content of a machine.
Each class of this model describes corresponding node of a machine.
There is a graphical editor which provides a schematic visualization of
machine content.
The editor contains a generator producing a module draft for the machine.

A generated machine draft contains most of the machine code.
It includes the initialization function and all the auxilary code.
The draft is also registered in QEMU build system and ready to build.

## Getting started

- *This manual is tested on Ubuntu 14.04.*
- *Compatibility with MS Windows OSes are not tested yet*
*but it is an objective.*

The toolset is written in Python.
Both 2.7 and 3.4 grammar are supported.

### Ubuntu Linux

Ubuntu 14.04 is already shipped with both Python version.
Tkinter is used as GUI back-end.
Hence install:

```bash
sudo apt install python-tk python3-tk
```

`idlelib` is also involved:

```bash
sudo apt install idle-python2.7 idle-python3.4
```

Note that `idle-python` package name suffix corresponds to the Python version.

`pip` is required to install several prerequesites.

```bash
sudo apt install python-pip python3-pip
```

QDT may adapt to changes in QEMU infrastructure.
It uses Git history to determine current version of the emulator.
The repository is analyzed using `gitpython` library.

```bash
sudo pip install gitpython
sudo pip3 install gitpython
```

`six` library is used to handle 2.x and 3.x Python version differences.

```bash
sudo pip install six
sudo pip3 install six
```

### Installation

QEMU Development Toolkit is suddenly required a QEMU to work with.
So, the first get its sources.

```bash
mkdir qemu
cd qemu
git clone git://git.qemu.org/qemu.git src
cd src
git checkout -b qdt_testing v2.9.0
git submodule init
git submodule update --recursive
```

QDT works with a build directory.
Hence, QEMU have to be configured first.
Of course, the QEMU build dependencies have to to be satisfied first.

```bash
sudo apt-get build-dep qemu
```

A good practice is to use out-of-source tree build.
And this manual follows it.

```bash
cd ..
mkdir build
cd build
../src/configure --target-list=i386-softmmu
```

The target list is shorted to speed up consequent building.
QDT is not limited to i386 CPU architecture.

It is time to get QDT.
Note that, several dependencies of QDT are embedded as submodules.

```bash
cd ..
git clone http://nasredin.intra.ispras.ru:3000/qemu/qdt.git qdt
cd qdt
git submodule init
git submodule update --recursive
```

Now you can launch the GUI.

```bash
./qdc-gui.py
```

An example project of Intel Q35 machine will be automatically loaded.

### Basic device stub generation

### Basic machine draft generation

### Combining

### Q35 Machine
