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
        self.c_type_name = c_type_name
        self.name = name
        self.array_size = array_size
        self.save_in_vmsd = save_in_vmsd
        self.is_property = is_property
        self.property_default = property_default
        self.property_name = property_name
        self.property_macro_suffix = property_macro_suffix

    def provide_property_name(self):
        property_name = self.property_name

        if property_name is None:
            property_name = '"' + self.name.replace('_', '-') + '"'

        return property_name

    def provide_property_macro_suffix(self):
        property_macro_suffix = self.property_macro_suffix

        if property_macro_suffix is None:
            property_macro_suffix = (
                self.provide_property_name()
                    .strip('"')
                    .replace('-', '_')
                    .upper()
            )

        return property_macro_suffix

    @property
    def need_save_in_vmsd(self):
        save_in_vmsd = self.save_in_vmsd
        if save_in_vmsd is None:
            return not bool(self.is_property)
        else:
            return save_in_vmsd

    def __var_base__(self):
        return "fld_"

    def __pygen_pass__(self, gen, __):
        gen.reset_gen(self)
        gen.gen_args(self, pa_names = True)
        gen.gen_end()

    def __repr__(self):
        gen = pygenerate(self)
        return gen.w.getvalue()[:-1] # remove extra new line
