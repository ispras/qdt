from docutils import (
    nodes,
)
from docutils.core import (
    publish_doctree,
    publish_from_doctree,
)
from docutils_rest_writer import (
    Writer,
)


with open("messages.rst", "r", encoding = "utf-8") as f:
    document = publish_doctree(f.read())

# print(document.pformat())

section = nodes.section()
title = nodes.title(text = "Второе сообщение")
section += title
paragraph = nodes.paragraph()
paragraph += nodes.Text("Сообщение с ")
paragraph += nodes.strong(text = "жирным")
paragraph += nodes.Text(" и ")
paragraph += nodes.emphasis(text = "курсивным")
paragraph += nodes.Text(" текстом.")
section += paragraph
document += section

rst_output = publish_from_doctree(document, writer = Writer())
with open("messages_modified.rst", "wb") as f:
    f.write(rst_output)
