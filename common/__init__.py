from topology import \
    sort_topologically, \
    GraphIsNotAcyclic

from pygen import \
    PyGenerator

from ml import \
    mlget, \
    ML

from co_dispatcher import \
    CoTask, \
    CoDispatcher

def sign(x): return 1 if x >= 0 else -1

from inverse_operation import \
    InverseOperation, \
    InitialOperationBackwardIterator, \
    UnimplementedInverseOperation, \
    InitialOperationCall, \
    History, \
    HistoryTracker

def unbind(tk_widget, sequence, funcid = None):
    if funcid is None:
        tk_widget.tk.call('bind', tk_widget._w, sequence, '')
    else:
        binded = tk_widget.tk.call("bind", tk_widget._w, sequence)

        new_binded = '\n'.join([ s for s in binded.split('\n') 
                             if s and not funcid in s ]) + '\n'

        tk_widget.tk.call("bind", tk_widget._w, sequence, new_binded)

        tk_widget.deletecommand(funcid)

from class_tools import \
    get_class, \
    get_class_defaults, \
    gen_class_args

from reflection import \
    get_default_args

from visitor import \
    ObjectVisitor, \
    BreakVisiting

from search_helper import \
    co_find_eq

from formated_string_var import \
    FormatedStringChangindException, \
    FormatVar, \
    FormatedStringVar
