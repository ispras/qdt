Text blocks
===========

.. workflow:: MR
   :tags: MR, feature
   :branch: txt_blocks
   :assignee: bda

Introduces a parser for text.
The parser returns a tree of blocks.
A block is sequence of lines with same indent.
A line with new indent initiates a new block.
The new block is child of previous line.
There is a stack of indents.
The stack corresponds to a tree path from the root to a current block.
Repeated indent removes top items of the stack till same indent.
And corresponding block becomes current again and continues
gathering lines.

This is very similar to Python's code block structure.
Except, a child may has **any unique** indent.
Uniqueness is relative to its ancestors, not entire text.
I.e. blocks with same depth may have different indents.
And an indent may be a prefix of blocks with different depth.

This parser is base for short instruction semantic format
(see ``devel`` branch).

Most of patches were not squashed for a historical reason.
They are to be considered one big patch.
Last patch adds ``misc/parse_blocks.py`` script.
It is just an example of the parser usage.

Обсуждение
----------
Добавил в конец ветки правку,
чтобы для пустого текста возвращалось пустое дерево.

Там ещё есть проблема с отступом первой строки.
Текущая версия требует, чтобы первая строка была без отступа.
Я планирую это исправить в позже.
Для кода и так норм.
А до обычного текста дело ещё не дошло.

Если последняя строка разбираемого текста не имеет переноса,
то она "теряется".
Это задуманное поведение?

Нет.
Конец файла должен считаться как перенос.

Требование возрастания отступов у детей специально не добавлялось?
Например, входной текст::
    A
        B
            C
          D

D будет ребенком C, а не B.
Задумка в "скрадывании" отступов детей, чтобы было больше места под полезный
текст в 80-символьной строке?

Да, это целевая фича, которой мне не хватает в Питоне::

    def function():
   """ multiline
   doc
   string
   """
   a = 1
   b = 2
   c = a + b

Причём табы и пробелы --- это разные отступы.
Сначала можно пользоуваться табами.
А, если код сильо разрастается в глубину,
то добавлять один пробел и снова начинать с табов.
Такой код в любом случае будет выглядеть отбито.
Тут нужен удобный текстовой редактор.

Также это лучще подходит для обычного текста::

          Книга
         Глава
        Раздел
       Подраздел
      Пункт
     Подпункт
    Абзац
   Текст абзаца
   Текст абзаца
   Текст абзаца
   Текст абзаца
   Текст абзаца

Логично, что самый массовый текст должен иметь наименьший отступ.
