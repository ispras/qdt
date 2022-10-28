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
        save_in_vmsd = None,
        is_property = False,
        property_default = None,
        property_name = None,
        property_macro_suffix = None,
    ):
        if property_name is None:
            property_name = '"' + name.replace('_', '-') + '"'

        if property_macro_suffix is None:
            property_macro_suffix = (
                property_name
                .strip('"')
                .replace('-', '_')
                .upper()
            )

        if save_in_vmsd is None:
            save_in_vmsd = not bool(is_property)

        self.c_type_name = c_type_name
        self.name = name
        self.array_size = array_size
        self.save_in_vmsd = save_in_vmsd
        self.is_property = is_property
        self.property_default = property_default
        self.property_name = property_name
        self.property_macro_suffix = property_macro_suffix

    def __var_base__(self):
        return "fld_"

    def __pygen_pass__(self, gen, __):
        gen.reset_gen(self)
        gen.gen_args(self, pa_names = True)
        gen.gen_end()

    def __repr__(self):
        gen = pygenerate(self)
        return gen.w.getvalue()[:-1] # remove extra new line
