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
