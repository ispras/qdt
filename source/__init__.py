from chunk import Chunk
from copy import copy
import this
from os.path import os

# Source code models

class Source():
    def __init__(self, path):
        self.path = path
        self.types = {}
        self.inclusions = {}
    
    def add_inclusion(self, header):
        if not type(header) == Header:
            raise Exception("Inclusion of non-header file {} is forbidden"
                .format(header.path))
        
        if not header.path in self.inclusions:
            self.inclusions[header.path] = header
        
        for name, t in header.types.items():
            if type(t) == TypeReference:
                self.types[name] = t
            else:
                self.types[name] = TypeReference(t, header)
        
        header.includers.append(self)
    
    def _add_type_recursive(self, type_ref):
        if type_ref.name in self.types:
            t = self.types[type_ref.name]
            if type(t) == TypeReference:
                # To check incomplete type case
                if not t.header == type_ref.header:
                    raise Exception("""Conflict reference to type {} \
found in source {}. The type is defined both in {} and {}.\
""".format(t.name, self.path, type_ref.path, t.path))
            # To make more conflicts checking
            return
        
        self.types[type_ref.name] = type_ref
    
    def add_type(self, _type):
        if type(_type) == TypeReference:
            raise Exception("""A type reference ({}) cannot be 
added to a source ({}) externally""".format(_type.name, self.path))
        
        _type.definer = self
        self.types[_type.name] = _type
        
        # Auto include type definers
        for s in _type.get_definers():
            if s == self:
                continue
            if not type(s) == Header:
                raise Exception("Attempt to define structure {} that has \
a field of a type defined in another non-header file {}.".format(
    _type.name, s.path))
            self.add_inclusion(s)
    
    def gen_chunks(self):
        chunks = []
        for h in self.inclusions.values():
            chunks.append(HeaderInclusion(h))
    
        for t in self.types.values():
            if t.definer == self:
                if type(t) == Function:
                    if type(self) == Header:
                        chunks.append(t.gen_chunk())
                    else:
                        chunks.append(t.gen_definition())
                else:
                    chunks.append(t.gen_chunk())
        
        return chunks
    
    def generate(self):
        basename = os.path.basename(self.path)
        name = os.path.splitext(basename)[0]
        
        file = SourceFile(name, type(self) == Header)
        
        file.add_chunks(self.gen_chunks())
        
        return file
        

class Header(Source):
    def __init__(self, path, is_global=False):
        super(Header, self).__init__(path)
        self.is_global = is_global
        self.includers = []
    
    def _add_type_recursive(self, type_ref):
        super(Header, self)._add_type_recursive(type_ref)
        
        for s in self.includers:
            s._add_type_recursive(type_ref)
    
    def add_type(self, _type):
        super(Header, self).add_type(_type)
        
        # Auto add type references to self includers
        type_ref = TypeReference(_type, self)
        
        for s in self.includers:
            s._add_type_recursive(type_ref)

# Type models

class Type():
    def __init__(self, name, incomplete=True, base=False):
        self.name = name
        self.incomplete = incomplete
        self.definer = None
        self.base = base
    
    def gen_var(self, name, pointer = False):
        if self.incomplete:
            if not pointer:
                raise Exception("Cannon create non-pointer variable {} \
of incomplete type {}.".format(name, self.name))

        if pointer:
            return Variable('*' + name, self)
        else:
            return Variable(name, self)

    def get_definers(self):
        if self.definer == None:
            return []
        else:
            return [self.definer]
    
    def gen_chunk(self):
        raise Exception("Attempt to generate source chunk for type {}"
            .format(self.name))
    
    def gen_defining_chunk(self):
        if self.definer == None:
            return None
        elif type(self.definer) == Header:
            return HeaderInclusion(self.definer)
        elif self.base:
            return None
        else:
            return self.gen_chunk()
    
    def gen_defining_chunk_list(self):
        d = self.gen_defining_chunk()
        if d == None:
            return []
        else:
            return [d]

# Base types

type_void = Type(name = "void", incomplete = True, base = True)
type_int = Type(name = "int", incomplete = False, base = True)

class TypeReference(Type):
    def __init__(self, _type, header):
        if type(_type) == TypeReference:
            raise Exception("Cannot create type reference to type \
reference {}.".format(_type.name))

        super(TypeReference, self).__init__(_type.name, _type.incomplete)
        self.header = header
        self.type = _type
        
    def get_definers(self):
        return self.type.get_definers()

    def gen_chunk(self):
        raise Exception("Attempt to generate source chunk for \
reference to type {}".format(self.name))

class Structure(Type):
    def __init__(self, name):
        super(Structure, self).__init__(name, incomplete=False)
        self.fields = []
    
    def get_definers(self):
        if self.definer == None:
            raise Exception("Getting definers for structure {} that \
is not added to a source", self.name)
        
        definers = [self.definer]
        
        for f in self.fields:
            definers.extend(f.type.get_definers())
        
        return definers
        
    
    def append_field(self, variable):
        for f in self.fields:
            if f.name == variable.name:
                raise Exception("""Field with name {} already exists
 in structure {}""".format(f.name, self.name))

        self.fields.append(variable)
    
    def append_field_t(self, _type, name, pointer = False):
        self.append_field(_type.gen_var(name, pointer))

    def gen_chunk(self):
        return StructureDeclaration(self)

class Function(Type):
    def __init__(self,
            name,
            body = None,
            ret_type = type_void,
            args = None,
            static = False, 
            inline = False,
            used_types = []):
        # args is list of Variables
        super(Function, self).__init__(name,
            # function cannot be a 'type' of variable. Only function
            # pointer type is permitted.
            incomplete=True)
        self.static = static
        self.inline = inline
        self.body = body
        self.ret_type = ret_type
        self.args = args
        self.used_types = used_types

    def gen_declaration(self):
        return FunctionDeclaration(self)
    
    def gen_definition(self):
        return FunctionDefinition(self)

    def gen_chunk(self):
        return self.gen_declaration()

# Data models

class Variable():
    def __init__(self, name, _type):
        self.name = name
        self.type = _type
    
    def gen_declaration_chunk(self, indent=""):
        return VariableDeclaration(self, indent)

# Function and instruction models

class Operand():
    def __init__(self, name, data_references=[]):
        self.name = name
        self.data_references = data_references

class VariableOperand(Operand):
    def __init__(self, var):
        super(VariableOperand, self).__init__(
            "reference to variable {}".format(var.name), [var])

class Operator():
    def __init__(self, fmt, operands):
        self.format = fmt
        self.operands = operands

class BinaryOperator(Operator):
    def __init__(self, name, operands):
        fmt = "{{}} {} {{}}".format(name);
        super(BinaryOperator, self).__init__(fmt, operands)

class AssignmentOperator(BinaryOperator):
    def __init__(self, operands):
        super(AssignmentOperator, self).__init__("=", operands)


class CodeNode():
    def __init__(self, name, code, used_types=None, node_references=None):
        self.name = name
        self.code = code
        self.node_users = []
        self.node_references = []
        self.used_types = []

# Source code instances

class SourceChunk:
    def __init__(self, name, code, references = None):
        # visited is used during deep first sort
        self.name = name
        self.code = code
        self.visited = 0
        self.users = []
        self.references = []
        self.source = None
        if not references == None:
            for chunk in references:
                self.add_reference(chunk)
    
    def add_reference(self, chunk):
        self.references.append(chunk)
        chunk.users.append(self)
    
    def del_reference(self, chunk):
        self.references.remove(chunk)
        chunk.users.remove(self)
    
    def check_cols_fix_up(self, max_cols = 80, indent='    '):
        lines = self.code.split('\n')
        code = ''
        auto_new_line = ' \\\n{}'.format(indent)
        
        for line in lines:
            if line == lines[-1] and len(line) == 0:
                break;

            if len(line) > max_cols:
                words = line.split(' ')
                ll = 0
                for word in words:
                    if ll > 0:
                        # The variable r reserves characters for auto new
                        # line ' \\' that can be added after current word 
                        if word == words[-1]:
                            r = 0
                        else:
                            r = 2
                        if 1 + r + len(word) + ll > max_cols:
                            code += auto_new_line + word
                            ll = 0
                        else:
                            code += ' ' + word
                            ll += 1 + len(word)
                    else:
                        code += word
                        ll += len(word)
                code += '\n'
            else:
                code += line + '\n'
        
        self.code = code

class HeaderInclusion(SourceChunk):
    def __init__(self, header):
        super(HeaderInclusion, self).__init__(
            name = "Header {} inclusion".format(header.path),
            references=[],
            code = """\
#include {}{}{}
""".format(
        ( "<" if header.is_global else "\"" ),
        header.path,
        ( ">" if header.is_global else "\"" ),
    )
            )
        self.header = header

class VariableDeclaration(SourceChunk):
    def __init__(self, var, indent=""):
        super(VariableDeclaration, self).__init__(
            name = "Variable {} of type {} declaration".format(
                var.name,
                var.type.name
                ),
            references = var.type.gen_defining_chunk_list(),
            code = """\
{indent}{type_name} {var_name};
""".format(
        indent = indent,
        type_name = var.type.name,
        var_name = var.name
    )
            )

class StructureDeclaration(SourceChunk):
    def __init__(self, struct, fields_indent="    ", indent=""):
        struct_begin = SourceChunk(
        name = "Beginning of structure {} declaration".format(struct.name),
        code = """\
{indent}typedef struct _{struct_name} {{  
""".format(
        indent = indent,
        struct_name = struct.name
    ),
        references = []
            )
        
        super(StructureDeclaration, self).__init__(
            name = "Ending of structure {} declaration".format(struct.name),
            code = """\
{indent}}} {struct_name};
""".format(
    indent = indent,
    struct_name = struct.name
    ),
            references = [struct_begin]
            )
        
        field_indent = "{}{}".format(indent, fields_indent)
        
        for f in struct.fields:
            field_declaration = f.gen_declaration_chunk(field_indent)
            field_declaration.add_reference(struct_begin)
            self.add_reference(field_declaration)

def gen_function_declaration_string(indent, function):
    if function.args == None:
        args = "void"
    else:
        args = ""
        for a in function.args:
            args += a.type.name + " " + a.name
            if not a == function.args[-1]:
                args += ", "

    return "{indent}{static}{inline}{ret_type}{name}({args})".format(
        indent = indent,
        static = "static " if function.static else "",
        inline = "inline " if function.inline else "",
        ret_type = function.ret_type.name + " ",
            name = function.name,
            args = args
    )

def gen_function_referenced_chunks(function):
    references = function.ret_type.gen_defining_chunk_list() 

    if not function.args == None:
        for a in function.args:
            references.extend(a.type.gen_defining_chunk_list())
    
    for t in function.used_types:
        references.extend(t.gen_defining_chunk_list())
    
    return references

class FunctionDeclaration(SourceChunk):
    def __init__(self, function, indent = ""):
        super(FunctionDeclaration, self).__init__(
            name = "Declaration of function %s" % function.name,
            references = gen_function_referenced_chunks(function),
            code = "%s;" % gen_function_declaration_string(indent, function)
            )

class FunctionDefinition(SourceChunk):
    def __init__(self, function, indent = ""):
        body = " {}" if function.body == None else "\n{\n%s}" % function.body
        super(FunctionDefinition, self).__init__(
            name = "Definition of function %s" % function.name,
            references = gen_function_referenced_chunks(function),
            code = "{dec}{body}\n".format(
                dec = gen_function_declaration_string(indent, function),
                body = body
                )
            )

def deep_first_sort(chunk, new_chunks):
    # visited: 
    # 0 - not visited
    # 1 - visited
    # 2 - added to new_chunks
    chunk.visited = 1
    for ch in chunk.references:
        if ch.visited == 2:
            continue
        if ch.visited == 1:
            raise Exception("A loop is found in source chunk references")
        deep_first_sort(ch, new_chunks)

    chunk.visited = 2
    new_chunks.append(chunk)

def source_chunk_key(ch):
    if type(ch) == HeaderInclusion:
        return 0
    else:
        return 1

class SourceFile:
    def __init__(self, name, is_header=False):
        self.name = name
        self.is_header = is_header
        self.chunks = []
        self.sort_needed = False

    def remove_dup_header_inclusions(self): 
        included_headers = {}
        
        for ch in list(self.chunks):
            if not type(ch) == HeaderInclusion:
                continue
            header = ch.header
            # key contains of 'g' or 'h' and header path
            # 'g' and 'h' are used to distinguish global and local
            # headers with same 
            key = "{}{}".format(
                "g" if header.is_global else "l",
                ch.header.path)
            
            try:
                inclusion = included_headers[key]
            except KeyError:
                included_headers[key] = ch
                continue
            
            # replace duplicate header references
            for user in list(ch.users):
                user.del_reference(ch)
                user.add_reference(inclusion)
            
            self.chunks.remove(ch)
            self.sort_needed = True
            

    def sort_chunks(self):
        if not self.sort_needed:
            return
        
        new_chunks = []
        # topology sorting
        for chunk in self.chunks:
            if not chunk.visited == 2:
                deep_first_sort(chunk, new_chunks)
        
        # semantic sort
        new_chunks.sort(key = source_chunk_key)
        
        self.chunks = new_chunks
    
    def add_chunks(self, chunks):
        for ch in chunks:
            self.add_chunk(ch)
    
    def add_chunk(self, chunk):
        if chunk.source == None:
            self.sort_needed = True
            self.chunks.append(chunk)
            
            # Also add referenced chunks into the source
            for ref in chunk.references:
                self.add_chunk(ref)
        elif not chunk.source == self:
            raise Exception("The chunk {} is already in {} ".format(
                chunk.name, chunk.source.name))
    
    def generate(self, writer, gen_debug_comments=False):
        self.remove_dup_header_inclusions()
        
        self.sort_chunks()
        
        writer.write("""
/* {}.{} */
""".format(
    self.name,
    "h" if self.is_header else "c"
    )
            )
        
        if self.is_header:
            writer.write("""\
#ifndef INCLUDE_{name}_H
#define INCLUDE_{name}_H
""".format(name = self.name.upper()))
        
        
        for chunk in self.chunks:
            
            chunk.check_cols_fix_up()
            
            if gen_debug_comments:
                writer.write("/* source chunk {} */\n".format(chunk.name))
            writer.write(chunk.code)
        
        if self.is_header:
            writer.write("""\
#endif /* INCLUDE_{}_H */
""".format(self.name.upper()))

class HeaderFile(SourceFile):
    def __init__(self, name):
        super(HeaderFile, self).__init__(name = name, is_header=True)
