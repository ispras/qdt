# Test naming convention

Base form: `{scope}_{operation}_{type}_{specifics}`.

## `scope`

* `a`: arithmetic operators (e.g. `+`, `*`).
* `c`: control flow (e.g., `if`, `for`, `goto`).
* `b`: bit logic (e.g., `|`, `&`, `^`).
* `s`: subprograms (e.g., call, `return`).
* `l`: logic operators (e.g., `||`, `&&`).
* `m`: memory access.
* `e`: all except above.

## `operation`

Target operation to test.

Form: `{word}{opt_word}`

### `word`

Any descriptive word.

* `add`: `+`.
* `sub`: `-`.
* `mul`: `*`.
* `div`: `/`.
* `or`: `|` or `||`, see `scope`.
* `and`: `&` or `&&`, see `scope`.
* `nand`: `~a & b`.
* `xor`: `^`.
* `br`: branch (likely, conditional).
   E.g., `if` block.
* `loop`: a loop, line `for` or `while`.
* `call`: a call of a function.
* `stack`: a call of a function that tests operands passing through stack.

### `opt_word`

Optional words.

Form: `_{word}{opt_word}`

## `type`

Type of target operands.
Target operand is the one which value is verified with oracle.

Form: `{specifiers}{size}`.

### `specifiers`

* `u`: unsigned (integer).
* `f`: floating-point.
* (*nothing*): signed (integer).

### `size`

Size of type in bits.
E.g. `f64` for `double`.

## `specifics`

More descriptive hints about the test.

Form: `{hints}{opt_N}`.

### `hints`

Form: `{hint}{opt_hints}`.

#### `hint`

* `v`: operand value is passed using a variable.
* `p`: ... pointer.
* `c`: ... constant.

* `eq`: `==`.
* `ne`: `!=`.
* `lt`: `<`.
* `le`: `<=`.
* `gt`: `>`.
* `ge`: `>=`.

* `js`, `bit`: names of assembler instructions.

#### `opt_hints`

Optional hints.

Form: `_{hint}{opt_hints}`

### `opt_N`

A zero based integer is used to avoid same file names when differences
between tests cannot be described using a sequence of `hint`s.

