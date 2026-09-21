# coding: utf-8

import re
import docutils.writers
import docutils.nodes
import docutils.parsers.rst.states


class Writer(docutils.writers.Writer):

    supported = ('rest',)
    """Formats this writer supports."""

    config_section = 'rest writer'
    config_section_dependencies = ('writers',)

    def __init__(self):
        docutils.writers.Writer.__init__(self)
        self.translator_class = Translator

    def translate(self):
        visitor = self.translator_class(self.document)
        self.document.walkabout(visitor)
        self.output = visitor.astext()


class Translator(docutils.nodes.NodeVisitor):

    def __init__(self, document):
        docutils.nodes.NodeVisitor.__init__(self, document)
        self.body = []
        self._stack = []
        self._section_depth = -1
        self._section_adornments = _section_adornments_sequence()

    def astext(self):
        return "".join(self.body)

    def visit_document(self, node):
        pass

    def depart_document(self, node):
        pass

    def visit_title(self, node):
        self._stack.append(("title", self.body))
        self.body = []

    def depart_title(self, node):
        title_body = "".join(self.body)
        tag, self.body = self._stack.pop()
        assert tag == "title"
        if self._section_depth < 0:
            header_formatter = self._section_adornments.pop(0)
        else:
            header_formatter = self._section_adornments[self._section_depth]
        self.body.append(header_formatter.format_header(title_body))

    def visit_subtitle(self, node):
        self._stack.append(("subtitle", self.body))
        self.body = []

    def depart_subtitle(self, node):
        title_body = "".join(self.body)
        tag, self.body = self._stack.pop()
        assert tag == "subtitle"
        assert self._section_depth < 0
        header_formatter = self._section_adornments.pop(0)
        self.body.append(header_formatter.format_header(title_body))

    def visit_block_quote(self, node):
        self._stack.append(("block_quote", self.body))
        self.body = []

    def depart_block_quote(self, node):
        quoted = ["    %s\n" % (l,) for l in "".join(self.body).splitlines()]
        tag, self.body = self._stack.pop()
        assert tag == "block_quote"
        self.body.append("".join(quoted))

    def visit_emphasis(self, node):
        self.body.append("*")

    def depart_emphasis(self, node):
        self.body.append("*")

    def visit_strong(self, node):
        self.body.append("**")

    def depart_strong(self, node):
        self.body.append("**")

    def visit_literal(self, node):
        self.body.append("``")

    def depart_literal(self, node):
        self.body.append("``")

    def visit_section(self, node):
        self._section_depth += 1

    def depart_section(self, node):
        self._section_depth -= 1

    def visit_paragraph(self, node):
        pass

    def depart_paragraph(self, node):
        self.body.append("\n\n")

    def visit_Text(self, node):
        escaped_text = re.sub(r'[*]', lambda match: {"*": "\\*"}[match.group()], node.astext())
        self.body.append(escaped_text)

    def depart_Text(self, node):
        pass


class SectionHeaderFormatter(object):

    def __init__(self, section_char, two_lines):
        self._section_char = section_char
        self._two_lines = two_lines

    def format_header(self, text):
        line = self._section_char * len(text)
        if self._two_lines:
            return "\n".join((line, text, line, "\n"))
        else:
            return "\n".join((text, line, "\n"))


def _section_adornments_sequence():
    return [SectionHeaderFormatter(separator, two_lines)
            for two_lines in (True, False)
            for separator in _compute_section_chars()]


def _compute_section_chars():
    # Recommended separators, reordered here. Source:
    # http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html#sections
    recommended_separators = "#*=-~:+\"'^`._"

    states = docutils.parsers.rst.states
    nonalphanum7bit = states.Body.pats["nonalphanum7bit"]
    ascii_chars = [chr(x) for x in range(128)]
    extra_separators = "".join(x for x in ascii_chars
            if x not in recommended_separators and re.match(nonalphanum7bit, x))
    return recommended_separators + extra_separators
