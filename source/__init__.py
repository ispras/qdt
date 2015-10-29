from chunk import Chunk
class Header():
    def __init__(self, path, is_global=False):
        self.path = path
        self.is_global = is_global

class TypeReference():
    def __init__(self, name, header=None):
        self.name = name
        self.header = header
    
    def gen_var(self, name):
        return Variable(name, self)

class Variable():
    def __init__(self, name, _type):
        self.name = name
        self.type = _type

class Structure():
    def __init__(self, name):
        self.name = name
        self.fields = []
    
    def append_field(self, variable):
        for f in self.fields:
            if f.name == variable.name:
                raise Exception("""Field with name {} already exists
 in structure {}""".format(f.name, self.name))

        self.fields.append(variable)
    
    def append_field_t(self, _type, name):
        self.append_field(_type.gen_var(name))

class SourceChunk:
    def __init__(self, name, code, references):
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
        header = var.type.header
        if header == None:
            references = []
        else:
            references = [HeaderInclusion(header)]
            
        super(VariableDeclaration, self).__init__(
            name = "Variable {} of type {} declaration".format(
                var.name,
                var.type.name
                ),
            references = references,
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
            field_declaration = VariableDeclaration(f, field_indent)
            field_declaration.add_reference(struct_begin)
            self.add_reference(field_declaration)


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

def source_chunk_ket(ch):
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
            

    def sort_chunks(self):
        if not self.sort_needed:
            return
        
        self.remove_dup_header_inclusions()
        
        new_chunks = []
        # topology sorting
        for chunk in self.chunks:
            if not chunk.visited == 2:
                deep_first_sort(chunk, new_chunks)
        
        # semantic sort
        new_chunks.sort(key = source_chunk_ket)
        
        self.chunks = new_chunks
    
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
