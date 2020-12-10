# Материалы

http://energia.nu/downloads/downloadv4.php?file=energia-1.8.10E23-linux64.tar.xz

http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/9_2_0_0/export/msp430-gcc-9.2.0.50_linux64.tar.bz2

http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/9_2_0_0/export/msp430-gcc-support-files-1.210.zip

https://www.eclipse.org/downloads/download.php?file=/technology/epp/downloads/release/2019-06/R/eclipse-java-2019-06-R-linux-gtk-x86_64.tar.gz

https://www.pydev.org/download.html

# Знакомство с Qemu

Некоторые зависимости для Qemu.

```
sudo apt install ninja-build
```

Скачать и собрать Qemu.

```
mkdir -p qemu/build
git clone https://git.qemu.org/git/qemu.git qemu/src
cd qemu/src
git checkout v5.1.0
# git submodule sync --recursive
git submodule update --init --recursive
cd ../build
../src/configure \
    --target-list=i386-softmmu \
    --prefix=$(cd .. && pwd)/install \
    --extra-cflags="-no-pie -gpubnames" \
    --disable-pie \
    --enable-debug

make -j8 install
cd ../..
```

Проверить.

```
qemu/install/bin/qemu-system-i386
```

_Порыться в исходниках Qemu_

# Автоматизированная разработка системы команд MSP430

Скачать QDT.

```
git clone https://github.com/ispras/qdt.git qdt/src
cd qdt/src
git checkout msp430
git submodule update --init --recursive
cd ../..
```

Скачать I3S.

```
git clone https://github.com/ispras/I3S.git i3s/src
cd i3s/src
git checkout i3s
# git submodule update --init --recursive
cd ../..
```

Открыть проект в графическом редакторе.
Дождаться построения кэша.
_Или скопировать готовый, чтобы не ждать._

```
qdt/src/qdc-gui.py -b qemu/build msp430/msp430_project.py &
```

Начать разработку.

```
cd qemu/src
git-cola &
gitk &
git checkout -b msp430 v5.1.0
# git submodule update --init --recursive
cd ../..
```

Запустить генерацию через ГИП (Ctrl-G) или командой.

```
qdt/src/qemu_device_creator.py \
    -b qemu/build \
    -t v5.1.0 \
    msp430/msp430_project.py
```

Посмотреть и зафиксировать текущее состояние.

Коррекция заготовки под 5.1.0

```
cd qemu/src
git am ../../patches/0001-msp430-update-old-style-boilerplate.patch
```

Удалить мертвый код из генерённой I3S-заготовки семантики.

```
git am ../../patches/0001-msp430-remove-dead-code-from-translate.inc.i3s.c.patch
cd ../..
```

Транслировать семантику.

```
python2 i3s/src/i3s_to_c.py \
    --in-file qemu/src/target/msp430/translate.inc.i3s.c \
    --out-file qemu/src/target/msp430/translate.inc.c
```

Зафиксировать изменения в Git.

Просмотреть разницу.

```
meld \
    qemu/src/target/msp430/translate.inc.i3s.c  \
    qemu/src/target/msp430/translate.inc.c
```

Исправить TCGMemOp.

```
cd qemu/src
git am ../../patches/0001-target-msp430-translate.inc.c-TCGMemOp-MemOp.patch
```

Доделать процессор, тестовую машину и аппаратный умножитель.

```
git am ../../patches/0001-MSP430-CPU-reset-interrupts-GDB-RSP-access.patch
git am ../../patches/0001-msp430_test-description-kernel-loading.patch
git am ../../patches/0001-msp430-all-implement-HWM.patch
```

Переконфигурировать эмулятор на MSP430 и собрать.

```
cd ../build

../src/configure \
    --target-list=msp430-softmmu \
    --prefix=$(cd .. && pwd)/install \
    --extra-cflags="-no-pie -gpubnames" \
    --disable-pie \
    --enable-debug

#     --extra-cflags="-Wno-error=maybe-uninitialized"

make -j8 install
cd ../..
```

Протестировать процессор с помощью C2T.

```
export MSP430_SUPPORT=$(pwd)/toolchain/msp430-gcc-support-files-1.210/msp430-gcc-support-files
export MSP430_TOOLCHAIN=$(pwd)/toolchain/msp430-gcc-9.2.0.50_linux64
export MSP430_QEMU=$(pwd)/qemu/install/bin/qemu-system-msp430

qdt/src/c2t.py \
    -t ^.+\\.c$ \
    -s ^_readme_.*$ \
    -s ^.*m_stack_u?((32)|(64)).*$ \
    -j 8 \
    -e 0 \
    $(pwd)/msp430/config_msp430g2553.py
```

Оценка покрытия.

```
PYTHONPATH=$(pwd)/qdt/src \
qdt/src/misc/msp430x_tests_coverage.py \
    --output msp430.cov.verbose.csv \
    --summary msp430x.cov.summary.csv \
    qdt/src/c2t/tests/ir
```

Сравнение с "камнем".

```
export MSP430_SUPPORT=\"$(pwd)/toolchain/msp430-gcc-support-files-1.210/msp430-gcc-support-files\"
export MSP430_TOOLCHAIN=\"$(pwd)/toolchain/msp430-gcc-9.2.0.50_linux64\"
export MSP430_TESTS_PATH=\"$(pwd)/msp430/tests\"
export QEMU_MSP430=\"$(pwd)/qemu/install/bin/qemu-system-msp430\"
export QEMU_MSP430_ARGS='["-M", "msp430_test", "-nographic"]'

PYTHONPATH=$(pwd)/qdt/src \
qdt/src/misc/msp430_test.py
```

Проверить разницу.

```
cd msp430/tests
./diff-all.sh
cd ../..
```

Посмотреть разницу.

```
export TEST=call_indexed_sp
meld msp430/tests/$TEST.qemu.log msp430/tests/$TEST.hw.log
```

Перепроверить конректный тест.

```
PYTHONPATH=$(pwd)/qdt/src \
qdt/src/misc/msp430_test.py call_indexed_sp
```

Сгенерировать заготовку msp430x2xx.

```
qdt/src/qemu_device_creator.py \
    -b qemu/build \
    -t v5.1.0 \
    msp430/msp430x2xx.py
```

Или через GUI.

```
qdt/src/qdc-gui.py \
    -b qemu/build \
    msp430/msp430x2xx.py &
```

Зафиксировать изменения через Git.

Реализовать машину и устройства.

```
cd qemu/src
git am ../../patches/0001-msp430x2xx-implement-some-devices-and-guest-loading-.patch
```

Пересобрать.

```
cd ../build
make -j8 install
cd ../..
```

Проверить.

```
qemu/install/bin/qemu-system-msp430 -M msp430x2xx
```

Выполнить в HMP.

```
info mtree
info qtree
```

Подготовить пример.

```
export ENERGIA_PATH=\"$(pwd)/energia-1.8.10E23-linux64/energia-1.8.10E23\"

# chmod +x qdt/src/misc/energia_build.py

PYTHONPATH=$(pwd)/qdt/src \
    qdt/src/misc/energia_build.py ASCIITable/ASCIITable.ino
```

Запуск примера в эмуляторе.

```
qemu/install/bin/qemu-system-msp430 \
    -M msp430x2xx \
    -kernel ASCIITable/ASCIITable.elf
```

Пример отладки совместной отладки гостя и Qemu в Eclipse.

Отладочная сборка эмулятора (не требуется, если использовались ялаги выше).

```
cd qemu/build

make distclean
../src/configure \
    --target-list=msp430-softmmu \
    --prefix=$(cd .. && pwd)/install \
    --extra-cflags="-no-pie -gpubnames" \
    --disable-pie \
    --enable-debug

make -j8 install
cd ../..
```

Отладка эмулятора с помощью QDT.

Отладка в QW (не робит на 5.1.0).

```
qdt/src/qw.py \
    -q $(pwd)/qemu/src \
    --verbose \
    -- \
    qemu/install/bin/qemu-system-msp430 \
    -M msp430_test \
    -kernel ASCIITable/ASCIITable.elf
```

Нужна версия v2.12.1.

````
cd qemu/src
git checkout v2.12.1 --force
git submodule sync --recursive
git submodule update --init --recursive
mkdir ../build_2.12.1
cd ../build_2.12.1
../src/configure \
    --target-list=i386-softmmu \
    --prefix=$(cd .. && pwd)/install_2.12.1 \
    --extra-cflags="-no-pie -gpubnames" \
    --disable-pie \
    --enable-debug

make -j8 install
cd ../..
```

Отладка в QW.

```
qdt/src/qw.py \
    -q $(pwd)/qemu/src \
    --verbose \
    -- \
    qemu/install_2.12.1/bin/qemu-system-i386
```



