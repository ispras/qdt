__all__ = [
    "DWARFInfoAccelerator"
]

from common import (
    bsep,
    lazy,
    trie_add,
    trie_find,
    intervalmap
)
from os.path import (
    join
)
from elftools.dwarf.callframe import (
    CIE
)
from .dwarf_expr_builder import (
    DWARFExprBuilder
)
from .expression import (
    Register,
    Plus
)


CU_INNER_REFS = set([
    "DW_FORM_ref1",
    "DW_FORM_ref2",
    "DW_FORM_ref4",
    "DW_FORM_ref8"
])


class DWARFInfoAccelerator(object):
    """ A helper class that implements some tricks to accelerate access to
pyelftools's `DWARFInfo`.
    """

    def __init__(self, di):
        self.di = di

        # accelerates access to compilation units (CU)
        self.idx2cu = []

        # A CU may be stored in DWARF with either full or relative file name.
        # But a user want to look CU up by its source root directory relative
        # path or just by file name (if there is only one source file with such
        # name). The method used in this mapping allows to look the CU up by
        # its path suffix if it is unique among all other CUs. A suffix tree
        # of dictionaries is used. See `_account_cu_by_reversed_name` for the
        # algorithm.
        self.name2cu = {}

        # CUs are parsed and accounted in mappings by demand. So, the iterator
        # do preserves parse state between demands.
        self._cu_parser_state = self._cu_parser()

        # Mapping of source positions to line program entries. An entry
        # contains the address and other useful information. There are
        # several levels in the mapping.
        # 1. file path suffix tree -> line interval map
        # 2. line interval -> list of line program entries
        # 3. some line intervals may produce different line program entries
        #    (e.g. function inlining). Hence, a list is used to store entries.
        self.srcmap = {}

        # Used to parse DWARF location expressions to high level symbolic model
        self.expr_builder = DWARFExprBuilder(di.structs)

        # Mapping of target addresses to Frame Description Entries of Call
        # Frame information.
        self.addr2fde = intervalmap()

        # Mapping of target addresses to rows of Call Frame Information table.
        self.addr2cfr = intervalmap()

        # Cache of CU file mappings.
        # CU's line program, subprogram's DW_AT_decl_file and so on refer to
        # files by numbers starting from 1. Mapping from numbers to file names
        # is computed during line program accounting. It's a list where 0-th
        # index corresponds to 1st file number. Those lists are stored in that
        # cache keyed by CU's offset.
        self.cu_off2files = {}

    @lazy
    def cfi(self):
        "Call Frame Information"
        di = self.di

        if di.has_CFI():
            return di.cfi
        elif di.has_EH_CFI():
            return di.eh_cfi
        else:
            # Actually this can be needed by DWARF location expressions to
            # get Canonical Frame Address.
            raise ValueError("No call frame information found")

    @lazy
    def _cfi_parser_state(self):
        "lazy `addr2fde` mapping building"
        return self._cfi_parser()

    @lazy
    def aranges(self):
        "Address Range Table"
        # DWARFInfo does not cache aranges and parses them for each request.
        # So, cache aranges in a lazy property.
        return self.di.get_aranges()

    def cu(self, addr):
        """ Compilation Unit

    :param addr:
        is a target's one
    :returns:
        compilation unit covering given address

        """

        cu_offset = self.aranges.cu_offset_at_addr(addr)
        # Note: _parse_CU_at_offset caches CUs those are already parsed
        cu = self.di._parse_CU_at_offset(cu_offset)
        return cu

    def cfa(self, addr):
        """ Canonical Frame Address

    :param addr:
        is a target's one
    :returns:
        symbolic expression for Canonical Frame Address

        """

        try:
            cfr = self.cfr(addr)
        except KeyError:
            cfr = None

        if cfr is None:
            raise KeyError("No CFR for address 0x%x" % addr)

        cfa = cfr["cfa"]
        expr = cfa.expr

        if expr is None:
            return Plus(Register(cfa.reg), cfa.offset)
        else:
            return self.expr_builder.build(expr)

    def cfr(self, addr):
        """ Call Frame information Row

    :param addr:
        is a target's one
    :returns:
        row of Call Frame Information table that describes address given.
        """
        addr2cfr = self.addr2cfr

        ret = addr2cfr[addr]

        if ret is None:
            # No such row parsed yet
            try:
                fde = self.fde(addr)
            except KeyError:
                fde = None

            if fde is None:
                raise KeyError("No row for address 0x%x" % addr)

            # account FDE`s table
            table_desc = fde.get_decoded()
            titer = iter(table_desc.table)

            prev_row = next(titer)
            for row in titer:
                addr2cfr[prev_row["pc"]:row["pc"]] = prev_row
                prev_row = row

            hdr = fde.header
            end = hdr.initial_location + hdr.address_range

            addr2cfr[prev_row["pc"]:end] = prev_row

            # search for row again
            ret = addr2cfr[addr]

        return ret

    def _cfi_parser(self):
        cfi = self.cfi
        offset = 0
        size = cfi.size
        parse = cfi._parse_entry_at

        while offset < size:
            e = parse(offset)
            yield e
            offset = e.instructions_end

    def fde(self, addr):
        """ Frame Description Entry

    :param addr:
        is a target's one
    :returns:
        Frame Description Entry actual for given address.

        """
        addr2fde = self.addr2fde
        fde = addr2fde[addr]

        if fde is None:
            for e in self._cfi_parser_state:
                if isinstance(e, CIE):
                    continue

                start = e.header.initial_location
                end = start + e.header.address_range
                addr2fde[start:end] = e

                # check if this FDE is one the caller looking for
                if addr < start:
                    continue
                if addr >= end:
                    continue

                fde = e
                break
            else:
                raise KeyError("No entry for address 0x%x" % addr)

        return fde

    def find_line_map(self, file_name):
        rpath = tuple(reversed(file_name.split(bsep)))
        try:
            lm, _ = trie_find(self.srcmap, rpath)
        except KeyError:
            try:
                cu = self.get_CU_by_reversed_path(rpath)
            except (KeyError, ValueError):
                # XXX: headers are not supported yet
                raise ValueError("Cannot find line program for file %s" % (
                    file_name
                ))

            self.account_line_program_CU(cu)
            lm, _ = trie_find(self.srcmap, rpath)
        except ValueError:
            raise ValueError("File name suffix '%s' is not long enough to"
                " unambiguously identify line map" % file_name)

        return lm

    def get_CU_files(self, cu):
        """
    :returns:
        mapping from CU's internal file indexes to split file paths

        """
        cache = self.cu_off2files
        offset = cu.cu_offset

        if offset not in cache:
            self.account_line_program_CU(cu)

        return cache[offset]

    def account_line_program_CU(self, cu):
        lp = self.di.line_program_for_CU(cu)

        entries = lp.get_entries()

        # Note that program entries must be parsed before header file list
        # access because DW_LNE_define_file operation adds new file entry
        # during entries parsing.

        hdr = lp.header
        fentries = hdr["file_entry"] # file_names
        dnames = hdr["include_directory"] # include_directories

        # first reconstruct contributing file paths
        files = []
        for f in fentries:
            dir_index = f["dir_index"]
            if dir_index == 0:
                # in current directory of the compilation
                _dir = ["."]
            else:
                # in include_directories section of the header
                _dir = dnames[dir_index - 1].split(bsep)
            name = f["name"].split(bsep)
            _path = _dir + name
            files.append(_path)

        self.cu_off2files[cu.cu_offset] = files

        srcmap = self.srcmap

        # To avoid double srcmap traversing (1. checking if a line map
        # already for a file and 2. adding a map if not) the attempt to add
        # an empty line map is always performed. If there is a map for the
        # file then trie_add returns it. If it returned given empty map then
        # this file is just added to srcmap and a new empty map should be
        # prepared for next file.
        empty_line_map = intervalmap()
        # cache of file line maps to prevent frequent search in srcmap
        line_maps = [None] * len(files)

        for e in entries:
            s = e.state
            if not s:
                # intermediate entries are not interested
                continue

            file_idx = s.file - 1
            line_map = line_maps[file_idx]

            if line_map is None:
                line_map = trie_add(srcmap, tuple(reversed(files[file_idx])),
                    empty_line_map
                )
                line_maps[file_idx] = line_map

            right_bound = s.line + 1
            if line_map is empty_line_map:
                # new file in srcmap, prepare new empty line map for next file
                empty_line_map = intervalmap()

                # This indirectly means that this entry (e) for this file is
                # first in the loop. Temporally occupy all lines above the line
                # of this entry. If there are entries whose occupied those
                # lines then the corresponding interval will be overwritten.
                # (0 because strange line number comes from LLVM 5.0.0)
                line_map[0:right_bound] = [e]
            else:
                # this file already is in srcmap
                left, right = line_map.interval(s.line)
                if right == right_bound:
                    line_map[left].append(e)
                else:
                    line_map[left: s.line + 1] = [e]

#             print("""
# command        = %u
# is_extended    = %r
# args           = %r
# address        = 0x%x
# file           = %s
# line           = %u
# column         = %u
# is_stmt        = %r
# basic_block    = %r
# end_sequence   = %r
# prologue_end   = %r
# epilogue_begin = %r
# isa            = %u
# """ % (
#     e.command, e.is_extended, e.args,
#     s.address,
#     sep.join(files[s.file - 1]), s.line, s.column,
#     s.is_stmt, s.basic_block, s.end_sequence, s.prologue_end,
#     s.epilogue_begin, s.isa
#             ))

    def _cu_parser(self):
        citer = self.di._parse_CUs_iter()
        idx2cu = self.idx2cu

        for cu in citer:
            idx2cu.append(cu)
            name = cu.get_top_DIE().attributes["DW_AT_name"].value
            parts = name.split(bsep)
            rparts = tuple(reversed(parts))
            self._account_cu_by_reversed_name(rparts, cu)

            yield cu, rparts

    def _account_cu_by_reversed_name(self, rparts, cu):
        # print("Accounting %s" % str(rparts))

        if trie_add(self.name2cu, rparts, cu) is not cu:
            raise RuntimeError("CU with path %s is already accounted" % (
                cu.get_top_DIE().attributes["DW_AT_name"].value
            ))

    def get_CU_by_idx(self, idx):
        idx2cu = self.idx2cu
        cu_count = len(idx2cu)

        if idx < cu_count:
            cu = idx2cu[idx]
        else:
            for i, (cu, _) in enumerate(self._cu_parser_state, cu_count):
                if i == idx:
                    break
            else:
                raise IndexError("Too big CU index %u" % idx)

        return cu

    def get_CU_by_name(self, suffix):
        parts = suffix.split(bsep)
        rparts = tuple(reversed(parts))
        return self.get_CU_by_reversed_path(rparts)

    def get_CU_by_reversed_path(self, rpath):
        rparts = rpath

        d = self.name2cu

        # scan suffix tree, starting from file name
        for i, p in enumerate(rparts, 1):
            if p not in d:
                # No such suffix yet. Continue DWARF info parsing.
                for _ in self._cu_parser_state:
                    if p in d:
                        break
                else:
                    # Parsing ended. No such CU.
                    break

            v = d[p]

            if isinstance(v, dict):
                # There are several CUs with such suffix. Try next suffix part.
                d = v
                continue

            # There is only one parsed CU with such suffix in the tree.
            cu, cu_rparts = v

            # Check parts of suffix those are not in the tree yet.
            if cu_rparts[:len(rparts) - i] == rparts[i:]:
                return cu
            else:
                # Some parts differs. Continue DWARF info parsing. It is
                # possible that the CU being looked for is not yet parsed.
                for _ in self._cu_parser_state:
                    v = d[p]
                    if not isinstance(v, tuple):
                        # New subtree appeared. Continue suffix matching.
                        d = v
                        break
                else:
                    # Parsing ended. No such CU.
                    break
        else:
            # Provided suffix is fully traversed. Is there a CU with exactly
            # such suffix?
            if None in d:
                return d[None]

            raise ValueError("Given name suffix %s is not long enough to look"
                " CU up. There are several CUs with such suffix." % join(
                    *reversed(rpath)
                )
            )

        raise KeyError("No CU with name suffix %s" % join(*reversed(rpath)))

    def iter_CUs(self):
        idx2cu = self.idx2cu
        ps = self._cu_parser_state

        i = 0
        while True:
            # idx2cu can be appended between yields. So, use explicit index i
            # as an invariant position.
            while i < len(idx2cu):
                yield idx2cu[i]
                i += 1

            # Parser can be adjusted between yields. Hence, take one CU per
            # time to avoid skips.
            try:
                cu, _ = next(ps)
            except StopIteration:
                # Explicitly catch StopIteration and return, see PEP 479
                return

            yield cu
            i += 1

    def get_CU_by_offset(self, offset):
        """
    :param offset:
        is relative to ".debug_info" section start
    :returns:
        the CU that covers given :offset:

        """

        cu = self.di._cu_cache[offset]

        if cu is None:
            # not parsed yet
            for cu, _ in self._cu_parser_state:
                # cu_boundary points to the byte just after last byte of the CU
                if cu.cu_boundary <= offset:
                    continue

        return cu

    def get_DIE_by_attr(self, attr, host_cu):
        """
    :param attr:
        is a DIE attribute that is reference to the DIE being searched.
    :host_cu
        the Compilation Unit containing the DIE containing the :attr:.
        It is required iff :attr: does point to a DIE inside the :host_cu:.
        `None` can be safely passed otherwise.

        """
        form = attr.form

        if form in CU_INNER_REFS:
            die = host_cu.get_DIE_at_offset(attr.value)
        elif form == "DW_FORM_ref_addr":
            offset = attr.value
            # get other CU by offset (type_attr.value) whithin it
            cu = self.get_CU_by_offset(offset)
            # compute inner offset
            inner = offset - cu.cu_offset
            # get the DIE
            die = cu.get_DIE_at_offset(inner)
        else: # form == "DW_FORM_ref_sig8":
            raise NotImplementedError("type in its own unit")

        return die
