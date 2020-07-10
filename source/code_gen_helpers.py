__all__ = [
    "gen_init_string"
  , "gen_function_declaration_string"
  , "gen_array_declaration"
]


def gen_init_string(_type, initializer, indent):
    init_code = ""

    if initializer is not None:
        raw_code = _type.gen_usage_string(initializer)
        # add indent to initializer code
        init_code_lines = raw_code.split('\n')
        init_code = "@b=@b" + init_code_lines[0]
        for line in init_code_lines[1:]:
            init_code += "\n" + indent + line

    return init_code


def gen_function_declaration_string(indent, function,
    pointer_name = None,
    array_size = None
):
    if function.args is None:
        args = "void"
    else:
        args = ",@s".join(a.declaration_string for a in function.args)

    return "{indent}{static}{inline}{ret_type}{name}(@a{args}@c)".format(
        indent = indent,
        static = "static@b" if function.static else "",
        inline = "inline@b" if function.inline else "",
        ret_type = function.ret_type.declaration_string,
        name = function.c_name if pointer_name is None else (
            "(*" + pointer_name + gen_array_declaration(array_size) + ')'
        ),
        args = args
    )


def gen_array_declaration(array_size):
    if array_size is not None:
        if array_size == 0:
            array_decl = "[]"
        elif array_size > 0:
            array_decl = '[' + str(array_size) + ']'
    else:
        array_decl = ""
    return array_decl
