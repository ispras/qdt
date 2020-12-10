#######
|title|
#######

.. |title| replace:: Добавление архитектуры процессора и периферии в Qemu
                     на примере микроконтроллера семейства msp430x2xx

Данный текст знакомит с методиками автоматизированного:

- добавления поддержки архитектуры процессора (MSP430);
- добавления моделей периферийных устройств;
- грубого тестирования архитектуры процессора;

с использованием QDT.

Материалы
=========

Обязательные
~~~~~~~~~~~~

- Среда разработки `Energia IDE <http://energia.nu/downloads/downloadv4.php?file=energia-1.8.10E23-linux64.tar.xz>`_

Energia IDE содержит в себе утилиты компиляции, вспомогательные файлы,
отладчик ``mspdebug``,
а также программные библиотеки для написания кода в Arduino-подобном
окружении и ряд вспомогательных программ и примеров кода.
В данном сценарии содержатся инструкции по использованию как Energia IDE,
так и необходимых компонентов, загружаемых по отдельности.

- `Утилиты компиляции MSP430 <http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/9_2_0_0/export/msp430-gcc-9.2.0.50_linux64.tar.bz2>`_

- `Вспомогательные файлы для утилит компиляции MSP430 <http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/9_2_0_0/export/msp430-gcc-support-files-1.210.zip>`_

- Отладчик ``mspdebug``::

	sudo apt install mspdebug

Опциональные
~~~~~~~~~~~~

Следующее будет полезно в случае выполнения продвинутых действий на
основе данного сценария.

- Среда разработки `Eclipse IDE <https://www.eclipse.org/downloads/download.php?file=/technology/epp/downloads/release/2019-06/R/eclipse-java-2019-06-R-linux-gtk-x86_64.tar.gz>`_

- Расширение `PyDev <https://www.pydev.org/download.html>`_ для среды
  разработки Eclipse IDE для программирования на языке Python.

Знакомство с Qemu
=================

Зависимости сборки
~~~~~~~~~~~~~~~~~~

Для сборки потребуются дополнительные библиотеки, которые могут отсутствовать
в системе.
Команды установки некоторых из них::

	sudo apt install ninja-build

Загрузка исходного кода
~~~~~~~~~~~~~~~~~~~~~~~

Обратите внимание, что полный путь директории, где выполняется данный
сценарий, не должен содержать пробельных символов и двоеточий, иначе
конфигурирование Qemu будет неудачным.
Также не стоит использовать одинарные и двойные кавычки, чтобы избежать
необходимости в экранировании.

Исходный код можно загрузить с помощью Git::

	mkdir -p qemu/build
	git clone https://gitlab.com/qemu-project/qemu.git qemu/src
	cd qemu/src
	git checkout v5.1.0
	# export GIT_SSL_NO_VERIFY=true # при проблемах с сертификатами
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

Автоматизированное добавление архитектуры MSP430
================================================

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

Открыть проект в графическом интерфейсе пользователя (ГИП)::

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
	    qdt/src/examples/MSP430/msp430/msp430_project.py

*Если кэш не был построен в ГИП ранее, данное действие может
занять около 10 минут.*

Посмотреть и зафиксировать текущее состояние::

	cd qemu/src
	git add -A
	git commit -m "MSP430: Generate boilerplate using QDT"
	cd ../..

В течение работы ``qemu_device_creator.py`` создаст файл
``translate.inc.i3s.c`` с семантикой инструкций (на основе описания
семантики из файлов ``msp430_sem.py`` и ``msp430x.py``) и автоматически
транслирует её в генератор промежуточного представления TCG
``translate.inc.c``.

Если перед генерацией через ГИП в меню
настроек была отключена автоматическая трансляция или семантика
была вручную дописана, то транслировать семантику можно так::

	python2 qdt/src/I3S/i3s_to_c.py \
	    --in-file qemu/src/target/msp430/translate.inc.i3s.c \
	    --out-file qemu/src/target/msp430/translate.inc.c

Зафиксировать изменения в Git (если была дополнительно транслирована
семантика)::

	cd qemu/src
	git add -A
	git commit -m "MSP430: Translate I3S to TCG API"
	cd ../..

Просмотреть разницу между описанием семантики на I3S и API TCG::

	meld \
	    qemu/src/target/msp430/translate.inc.i3s.c \
	    qemu/src/target/msp430/translate.inc.c \
	    &

Минимальный набор устройств
---------------------------

Доделать процессор, тестовую машину и аппаратный умножитель::

	cd qemu/src
	git am ../../qdt/src/examples/MSP430/patches/MSP430-CPU-reset-interrupts-GDB-RSP-access.patch
	git am ../../qdt/src/examples/MSP430/patches/msp430_test-description-kernel-loading.patch
	git am ../../qdt/src/examples/MSP430/patches/msp430-all-implement-HWM.patch
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

Рассмотрим тестирование добавленной архитектуры двумя способами:

- грубое тестирование, основанное на проверке логики работы программы
  на уровне языка Си;
- сравнение с настоящим микроконтроллером.

Проверка на уровне языка Си
```````````````````````````

Проверка архитектуры на уровне языка Си основывается на гипотезе, что
детерминированная программа, написанная на языке Си (некоторое подмножество
программ), должна работать одинаково независимо от вычислителя
(т.е. должен быть пройден точно такой же путь выполнения, должны совпадать
значения в переменных и т.п.).
Таким образом, если скомпилировать программу под основную машину (напр.,
AMD64) и проверяемую, а затем запустить под отладчиком на обеих, контролируя
вычислительный процесс на уровне абстракций языка Си (значения переменных,
номера строк выполняемых инструкций), то, в случае корректной реализации
проверяемой архитектуры, выполнение не должно иметь наблюдаемых отличий.

Хотя данный подход не позволяет проверить всю реализацию (т.к. есть
ряд условий и ситуаций, проверка работы в которых не выражается на языке Си),
грубые ошибки успешно обнаруживаются.

Загрузить утилиты компиляции и вспомогательные файлы::

	wget http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/9_2_0_0/export/msp430-gcc-9.2.0.50_linux64.tar.bz2
	wget http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/9_2_0_0/export/msp430-gcc-support-files-1.210.zip

Распаковать архивы::

	tar -xf msp430-gcc-9.2.0.50_linux64.tar.bz2
	unzip msp430-gcc-support-files-1.210

Протестировать процессор с помощью C2T::

	export MSP430_SUPPORT=$(pwd)/msp430-gcc-support-files
	export MSP430_TOOLCHAIN=$(pwd)/msp430-gcc-9.2.0.50_linux64
	export MSP430_QEMU=$(pwd)/qemu/install/bin/qemu-system-msp430

	qdt/src/c2t.py \
	    -t ^.+\\.c$ \
	    -s ^_readme_.*$ \
	    -s ^.*m_stack_u?((32)|(64)).*$ \
	    -j 8 \
	    -e 0 \
	    qdt/src/examples/MSP430/msp430/config_msp430g2553.py

Оценить покрытие::

	PYTHONPATH=$(pwd)/qdt/src \
	qdt/src/misc/msp430x_tests_coverage.py \
	    --output msp430.cov.verbose.csv \
	    --summary msp430x.cov.summary.csv \
	    qdt/src/c2t/tests/ir

Сценарии, находящиеся **не** в корневом каталоге QDT, требуют для работы
добавления корневого каталога в `PYTHONPATH`.

Сравнение с настоящим микроконтроллером
```````````````````````````````````````

Тесты, не формулируемые на языке Си, а также нюансы, не достаточно подробно
освещённые в документации, могут быть проверены путём запуска кода,
написанного на ассемблере, на настоящем МК.

Сравнить с "камнем"::

	export MSP430_SUPPORT=\"$(pwd)/msp430-gcc-support-files\"
	export MSP430_TOOLCHAIN=\"$(pwd)/msp430-gcc-9.2.0.50_linux64\"
	export MSP430_TESTS_PATH=\"$(pwd)/qdt/src/examples/MSP430/msp430/tests\"
	export QEMU_MSP430=\"$(pwd)/qemu/install/bin/qemu-system-msp430\"
	export QEMU_MSP430_ARGS='["-M", "msp430_test", "-nographic"]'

	PYTHONPATH=$(pwd)/qdt/src \
	qdt/src/misc/msp430_test.py

Наличие ``"`` или ``'`` вокруг значений переменных обязательно, т.к. значения
являются вычисляемыми выражениями на языке Python (в данном случае строками).

Также сравнение можно провести, используя Energia IDE.

Загрузить Energia IDE::

	wget -O energia-1.8.10E23-linux64.tar.xz http://energia.nu/downloads/downloadv4.php?file=energia-1.8.10E23-linux64.tar.xz

Распаковать архив::

	tar -xf energia-1.8.10E23-linux64.tar.xz

Сравнить с "камнем"::

	export ENERGIA_PATH=\"$(pwd)/energia-1.8.10E23\"
	export MSP430_TESTS_PATH=\"$(pwd)/qdt/src/examples/MSP430/msp430/tests\"
	export QEMU_MSP430=\"$(pwd)/qemu/install/bin/qemu-system-msp430\"
	export QEMU_MSP430_ARGS='["-M", "msp430_test", "-nographic"]'

	PYTHONPATH=$(pwd)/qdt/src \
	qdt/src/misc/msp430_test.py

После выполнения сценария ``msp430_test.py`` одним из вышеуказанных способов
можно вычислить разницу::

	cd qdt/src/examples/MSP430/msp430/tests
	./diff-all.sh
	cd ../../../../../..

Посмотреть разницу::

	export TEST=call_indexed_sp
	meld \
	    qdt/src/examples/MSP430/msp430/tests/$TEST.qemu.log \
	    qdt/src/examples/MSP430/msp430/tests/$TEST.hw.log \
	    &

Перепроверить конкретный тест::

	PYTHONPATH=$(pwd)/qdt/src \
	qdt/src/misc/msp430_test.py call_indexed_sp

Реализация модели ВМ семейства msp430x2xx
-----------------------------------------

Сгенерировать заготовку msp430x2xx::

	qdt/src/qemu_device_creator.py \
	    -b qemu/build \
	    qdt/src/examples/MSP430/msp430/msp430x2xx.py

Или через ГИП::

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
	git am ../../qdt/src/examples/MSP430/patches/msp430x2xx-implement-some-devices-and-guest-loading.patch
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

Запуск скетча
`````````````

Также можно запустить в эмуляторе "скетч", скомпилированный в Energia IDE.

Скетч `ASCIITable <ASCIITable/ASCIITable.ino>`_ является примером,
поставляемым в составе Energia IDE.
Он рассчитан на работу на настоящем микроконтроллере.
Его функция заключается в выводе на UART таблицы ASCII.

Загрузить скетч в IDE, выбрав в меню::

	Файл > Примеры > 04. Communication > ASCIITable

Сборку скетча следует производить, выбрав правильный МК в меню::

	Инструменты > Плата > MSP-EXP430G2 w/ MSP430G2553

Energia IDE не выдаёт собранные ELF файлы явно.
Однако путь можно найти в консоли, если включить опцию
"Показать подробный вывод" для компиляции в "Файл > Настройки".

Произвести компиляцию скетча, выбрав в меню::

	Скетч > Проверить/Компилировать

Запустить в эмуляторе скетч, скомпилированный в Energia IDE
(поправьте путь на свой)::

	qemu/install/bin/qemu-system-msp430 -M msp430x2xx -kernel /tmp/arduino_build_19993/ASCIITable.ino.elf

Увидеть результат работы можно, переключившись на вкладку виртуального
терминала Qemu, подключённого к UART МК (Ctrl-Alt-2 или через меню
"View" (если Qemu собран с GTK)).

Текущая реализация модели msp430x2xx является неполной.
Ввиду чего запуск многих других примеров из Energia IDE будет безуспешным.

