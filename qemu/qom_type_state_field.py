__all__ = [
    "QOMTypeStateField"
]

from common import (
    pygenerate,
)


class QOMTypeStateField(object):

    def __init__(self,
        c_type_name,
        name,
        array_size = None,
        save_in_vmsd = True,
        is_property = False,
        property_default = None
    ):
        self.c_type_name = c_type_name
        self.name = name
        self.array_size = array_size
        self.save_in_vmsd = save_in_vmsd
        self.is_property = is_property
        self.property_default = property_default

    def __var_base__(self):
        return "fld_"

    def __pygen_pass__(self, gen, __):
        gen.reset_gen(self)
        gen.gen_args(self, pa_names = True)
        gen.gen_end()

    def __repr__(self):
        gen = pygenerate(self)
        return gen.w.getvalue()[:-1] # remove extra new line
