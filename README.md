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

## Getting started

- *This manual is tested on Ubuntu 14.04 and Debian 7.11.*
- *Compatibility with MS Windows OSes are not tested yet*
*but it is an objective.*

The toolset is written in Python.
Both 2.7.3+ and 3.3+ versions are supported.

### Ubuntu Linux

Ubuntu 14.04 is already shipped with both 2.x and 3.x Python.
But several prerequisites are not installed by default.

Tkinter is used as GUI back-end.

```bash
sudo apt install python-tk python3-tk
```

`idlelib` is also involved.

```bash
sudo apt install idle-python2.7 idle-python3.4
```

Note that `idle-python` package name suffix corresponds to the Python version.

`pip` is required to install several prerequisites.

```bash
sudo apt install python-pip python3-pip
```

QDT adapts to changes in QEMU infrastructure.
It has a set of heuristics referring to specific commits in QEMU Git history.
`gitpython` package is used to analyze Git graph and get effective heuristics
for the current QEMU version.

```bash
sudo pip install gitpython
sudo pip3 install gitpython
```

`six` package is used to handle 2.x and 3.x Python version differences.

```bash
sudo pip install six
sudo pip3 install six
```

Now the all environment prerequisites are satisfied.

### Debian Linux

Debian 7.11 environment preparation is same as the one for Ubuntu 14.04
except for several specifics.

- `apt-get` command must be used everywhere instead of `apt`

- Python 3.2 grammar version is too old and does not supported by the toolset.
I.e. only Python 2 can be used.

- `python-pip` package is too old.
Hence, consider
[another](https://unix.stackexchange.com/questions/182308/install-python-pip-in-debian-wheezy)
way to install `pip`.

```bash
wget https://bootstrap.pypa.io/get-pip.py
sudo python get-pip.py
```

### Installation

QDT is suddenly required a QEMU to work with.
So, the first objective is to get its sources.

```bash
mkdir qemu
cd qemu
git clone git://git.qemu.org/qemu.git src
cd src
git checkout -b qdt_testing v2.9.0
git submodule init
git submodule update --recursive
```

The toolset works with a build directory.
Hence, QEMU build system have to be configured.
Of course, the QEMU build dependencies must be satisfied first.

```bash
sudo apt-get build-dep qemu
```

A good practice is to use out-of-source tree build.
And this manual follows it.

```bash
cd ..
mkdir build
cd build
../src/configure --target-list=moxie-softmmu
```

The target list is shorted to speed up consequent building.
QDT is not limited to moxie CPU architecture.

It is time to get QDT itself.
Note that, several dependencies of QDT are embedded as submodules.

```bash
cd ..
git clone http://nasredin.intra.ispras.ru:3000/qemu/qdt.git
cd qdt
git submodule init
git submodule update --recursive
```

Now you can launch the GUI.

```bash
./qdc-gui.py
```

An example project of Intel Q35 machine will be automatically loaded.
Do nothing if you wish to pass consequent examples without troubles.
Just check it works and close the main windows without saving the project.

### Basic device stub generation

To generate a device stub the two steps should be made.

1. Create a Python script with generation parameters.
2. Pass the script to the command line generator tool `qemu_device_creator.py`.

Simple `basic-device.py` script content is listed below.

```python
uart_desc = SysBusDeviceDescription(
    # name =
    "UART",
    # directory =
    "char"
)
p = QProject([uart_desc])
```

No imports are required.
The generator will provide all necessary names by self.

`SysBusDeviceDescription` class is a container for parameters of system
bus device generation.
There are only two parameters provided.

- `name` is a base for generation of new QOM type name, macro, function names
and so on.
It will be transformed according to C syntax and QEMU coding style.
See resulting code if interesting.

- `directory` is the name of subdirectories in "hw" and "include/hw".
Generated module and header will be placed in corresponding subdirectories.
Note that devices are grouped according to semantic.

Note that `name` and `directory` arguments are actually commented out by
`#` prefix.
This means that they are positional and those names can be skipped.
A Keyword argument is always set using its name across this manual.

All generation parameters must be packed in a project (`QProject`).
The generator expects one `QProject` in the input script.

Now the device model stub can be generated.

*Note that during first launch the generator will analyze QEMU sources.*
It is a time-consuming operation.
A few minutes are commonly required to complete.
The result of this analyze will be cached in the build directory.
An analyze is required each time the QEMU version (HEAD) changes.

```bash
cd ..
qdt/qemu_device_creator.py -b ./build basic-device.py
```

Now look at the changes on QEMU sources.

```bash
cd src
git status
```

Two new files should be created:

- `hw/char/uart.c`
- `include/hw/char/uart.h`

Also `hw/char/Makefile.objs` file should be changed.
QDT registered new device in QEMU build system.

### Basic machine draft generation

### Simple composite project

### Q35 Machine
