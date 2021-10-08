Материалы
=========

Обязательные
~~~~~~~~~~~~

- Среда разработки `Energia IDE <http://energia.nu/downloads/downloadv4.php?file=energia-1.8.10E23-linux64.tar.xz>`_

- `Утилиты компиляции MSP430 <http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/9_2_0_0/export/msp430-gcc-9.2.0.50_linux64.tar.bz2>`_

- `Вспомогательные файлы для утилит компиляции MSP430 <http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/9_2_0_0/export/msp430-gcc-support-files-1.210.zip>`_

Опциональные
~~~~~~~~~~~~

- Среда разработки `Eclipse IDE <https://www.eclipse.org/downloads/download.php?file=/technology/epp/downloads/release/2019-06/R/eclipse-java-2019-06-R-linux-gtk-x86_64.tar.gz>`_

- Расширение `PyDev <https://www.pydev.org/download.html>`_ для среды
  разработки Eclipse IDE для программирования на языке Python.

Знакомство с Qemu
=================

Зависимости сборки
~~~~~~~~~~~~~~~~~~

Для сборки потребуются дополнительные библиотеки, которые могут отсутствовать
в системе.
Команды установки некоторых их них::

	sudo apt install ninja-build


Загрузка исходного кода
~~~~~~~~~~~~~~~~~~~~~~~

Исходный код можно загрузить с помощью Git::

	mkdir -p qemu/build
	git clone https://git.qemu.org/git/qemu.git qemu/src
	cd qemu/src
	git checkout v5.1.0
	# git submodule sync --recursive
	git submodule update --init --recursive
	cd ../..

Сборка
~~~~~~

::

	cd qemu/build
	../src/configure \
	    --target-list=i386-softmmu \
	    --prefix=$(cd .. && pwd)/install \
	    --extra-cflags="-no-pie -gpubnames" \
	    --disable-pie \
	    --enable-debug

	make -j8 install
	cd ../..

Проверочный запуск
~~~~~~~~~~~~~~~~~~

::

	qemu/install/bin/qemu-system-i386

Чистка исходного кода после сборки
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

	cd qemu/src
	git reset --hard
	cd ../..

Автоматизированная разработка системы команд MSP430
===================================================

Загрузка Qemu Development Toolkit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

	git clone https://github.com/ispras/qdt.git qdt/src
	cd qdt/src
	git submodule update --init --recursive
	cd ../..

Первое открытие проекта
~~~~~~~~~~~~~~~~~~~~~~~

*Это действие можно пропустить.*

Открыть проект в графическом редакторе::

	qdt/src/qdc-gui.py \
	    -b qemu/build \
	    qdt/src/examples/MSP430/msp430/msp430_project.py \
	    &

Дождаться построения кэша.
Это может занять несколько десятков минут.

Разработка
~~~~~~~~~~

Создание отдельной ветки
------------------------

::

	cd qemu/src
	git-cola &
	gitk &
	git checkout -b msp430 v5.1.0
	# git submodule update --init --recursive
	cd ../..

Генерация заготовки
-------------------

Запустить генерацию через ГИП (Ctrl-G) или командой::

	qdt/src/qemu_device_creator.py \
	    -b qemu/build \
	    -t v5.1.0 \
	    qdt/src/examples/MSP430/msp430/msp430_project.py

Посмотреть и зафиксировать текущее состояние::

	cd qemu/src
	git add -A
	git commit -m "MSP430: Generate boilerplate using QDT"
	cd ../..

Транслировать семантику (если перед генерацией через ГИП в меню
настроек была отключена автоматическая трансляция или семантика
была вручную дописана)::

	python2 qdt/src/I3S/i3s_to_c.py \
	    --in-file qemu/src/target/msp430/translate.inc.i3s.c \
	    --out-file qemu/src/target/msp430/translate.inc.c

Зафиксировать изменения в Git (если была дополнительно транслирована
семантика)::

	cd qemu/src
	git add -A
	git commit -m "MSP430: Translate I3S to TCG API"
	cd ../..

Просмотреть разницу::

	meld \
	    qemu/src/target/msp430/translate.inc.i3s.c  \
	    qemu/src/target/msp430/translate.inc.c \
	    &

Минимальный набор устройств
---------------------------

Доделать процессор, тестовую машину и аппаратный умножитель::

	cd qemu/src
	git am ../../qdt/src/examples/MSP430/patches/0001-MSP430-CPU-reset-interrupts-GDB-RSP-access.patch
	git am ../../qdt/src/examples/MSP430/patches/0001-msp430_test-description-kernel-loading.patch
	git am ../../qdt/src/examples/MSP430/patches/0001-msp430-all-implement-HWM.patch
	cd ../..

Сборка
------

Переконфигурировать эмулятор на MSP430 и собрать::

	cd qemu/build

	../src/configure \
	    --target-list=msp430-softmmu \
	    --prefix=$(cd .. && pwd)/install \
	    --extra-cflags="-no-pie -gpubnames" \
	    --disable-pie \
	    --enable-debug

	#    --extra-cflags="-Wno-error=maybe-uninitialized"

	make -j8 install
	cd ../..

Тестирование
------------

Протестировать процессор с помощью C2T::

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

Оценка покрытия::

	PYTHONPATH=$(pwd)/qdt/src \
	qdt/src/misc/msp430x_tests_coverage.py \
	    --output msp430.cov.verbose.csv \
	    --summary msp430x.cov.summary.csv \
	    qdt/src/c2t/tests/ir

Сравнение с "камнем"::

	export MSP430_SUPPORT=\"$(pwd)/toolchain/msp430-gcc-support-files-1.210/msp430-gcc-support-files\"
	export MSP430_TOOLCHAIN=\"$(pwd)/toolchain/msp430-gcc-9.2.0.50_linux64\"
	export MSP430_TESTS_PATH=\"$(pwd)/msp430/tests\"
	export QEMU_MSP430=\"$(pwd)/qemu/install/bin/qemu-system-msp430\"
	export QEMU_MSP430_ARGS='["-M", "msp430_test", "-nographic"]'

	PYTHONPATH=$(pwd)/qdt/src \
	qdt/src/misc/msp430_test.py

Вычислить разницу::

	cd msp430/tests
	./diff-all.sh
	cd ../..

Посмотреть разницу::

	export TEST=call_indexed_sp
	meld msp430/tests/$TEST.qemu.log msp430/tests/$TEST.hw.log

Перепроверить конректный тест::

	PYTHONPATH=$(pwd)/qdt/src \
	qdt/src/misc/msp430_test.py call_indexed_sp

Реализация модели ВМ семецства msp430x2xx
-----------------------------------------

Сгенерировать заготовку msp430x2xx::

	qdt/src/qemu_device_creator.py \
	    -b qemu/build \
	    -t v5.1.0 \
	    qdt/src/examples/MSP430/msp430/msp430x2xx.py

Или через GUI::

	qdt/src/qdc-gui.py \
	    -b qemu/build \
	    qdt/src/examples/MSP430/msp430/msp430x2xx.py \
	    &

Зафиксировать изменения через Git::

	cd qemu/src
	git add -A
	git commit -m "MSP430: msp430x2xx family boilerplate"
	cd ../..

Реализовать машину и устройства::

	cd qemu/src
	git am ../../qdt/src/examples/MSP430/patches/0001-msp430x2xx-implement-some-devices-and-guest-loading-.patch
	cd ../..

Пересобрать::

	cd qemu/build
	make -j8 install
	cd ../..

Проверка
--------

Проверить::

	qemu/install/bin/qemu-system-msp430 -M msp430x2xx

Выполнить в HMP::

	info mtree
	info qtree
