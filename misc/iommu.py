#!/usr/bin/python

from subprocess import (
    Popen,
    PIPE,
)
from os.path import (
    exists,
    expanduser,
    split,
    join,
    sep,
)
from os import (
    environ,
    listdir,
)
from six.moves.tkinter import (
    Entry,
    Label,
    StringVar,
    LEFT,
    RIGHT,
    Checkbutton,
    BooleanVar,
    Button,
    Frame,
    Menu,
    NONE,
    END,
    Tk,
)
from six.moves.tkinter_ttk import (
    Sizegrip,
    Treeview,
)
from collections import (
    OrderedDict,
)
from difflib import (
    unified_diff,
)
from six import (
    PY3,
)
from re import (
    compile,
)
from types import (
    GeneratorType,
)
from traceback import (
    print_exc,
)
from threading import (
    Thread,
)
from six.moves.queue import (
    Empty,
    Queue,
)
from sys import (
    argv,
)
from common import (
    Persistent,
    bidict,
    lazy,
)
from widgets import (
    TkPopupHelper,
    GUIText,
    READONLY,
    GUIDialog,
    add_scrollbars_native,
)

if PY3:

    def s(r):
        return r.decode("utf-8")

else:
    s = lambda x : x

ROOT = sep
IOMMU_GROUPS = join(ROOT, "sys", "kernel", "iommu_groups")
LOCAL_CONF = join(ROOT, "etc", "modprobe.d", "local.conf")


class CLICommand(GUIDialog):

    def __init__(self, master, cmd_args, *a, **kw):
        GUIDialog.__init__(self, master, *a, **kw)

        self.title(" ".join(cmd_args))

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self.text = text = GUIText(self, state = READONLY, wrap = NONE)
        text.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, text)

        self.proc = Popen(cmd_args,
            stdout = PIPE,
            stderr = PIPE,
            stdin = PIPE,
            shell = True
        )

        text.tag_config("e", foreground = "red")
        text.tag_config("misc", foreground = "blue")

        self.qin, self.qerr, self.qout = Queue(), Queue(), Queue()

        self.threads = [
            Thread(
                target = self.stream_reader,
                args = (self.proc.stdout, self.qout)
            ),
            Thread(
                target = self.stream_reader,
                args = (self.proc.stderr, self.qerr)
            ),
            Thread(
                target = self.stream_writer,
                args = (self.proc.stdin, self.qin)
            ),
        ]
        for t in self.threads:
            t.start()

        self.after(5, self.proc_output)

        self.bind("<Key>", self.input, "+")
        self.bind("<Destroy>", self.__on_destroy, "+")

    def __on_destroy(self, e):
        if e.widget is not self:
            return
        if self.proc.poll() is None:
            self.proc.terminate()

    def input(self, e):
        data = e.char
        if not data:
            return
        self.qin.put(data)

    def proc_output(self):
        while not self.qout.empty():
            self.text.insert(END, s(self.qout.get()))
        while not self.qerr.empty():
            self.text.insert(END, s(self.qerr.get()), "e")
        ret = self.proc.returncode
        if ret is None:
            self.after(5, self.proc_output)
        else:
            self.text.insert(END, "Terminated with code %s\n" % ret, "misc")

    def stream_reader(self, stream, queue):
        p = self.proc
        line = b""
        while True:
            b = stream.read(1)
            if len(b) < 1:
                if p.poll() is not None:
                    break
            line += b
            if b == b"\n":
                queue.put(line)
                line = b""

    def stream_writer(self, stream, queue):
        p = self.proc
        while p.poll() is None:
            try:
                w = queue.get(timeout = 0.1)
            except Empty:
                continue
            print("-" + w + "-")
            stream.write(w)
            stream.flush()


class RootCommitDialog(GUIDialog):

    def __init__(self, master, kind, text4user, *a, **kw):
        GUIDialog.__init__(self, master, *a, **kw)

        self.title(kind)

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        text = GUIText(self, state = READONLY, wrap = NONE)
        text.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, text)

        text.insert(END, text4user)

        self.rowconfigure(2, weight = 0)

        btframe = Frame(self)
        btframe.grid(row = 2, column = 0, columnspan = 2, sticky = "NESW")

        btframe.rowconfigure(0, weight = 1)
        btframe.columnconfigure(0, weight = 0)

        Button(btframe, text = "Commit", command = self._on_commit).grid(
            row = 0, column = 0, sticky = "NESW"
        )
        Button(btframe, text = "Discard", command = self.destroy).grid(
            row = 0, column = 1, sticky = "NESW"
        )

    def _on_commit(self):
        self._result = True
        self.destroy()


class SuDoFailed(RuntimeError): pass


def root_commit(tk, path, new_content):
    if exists(path):
        with open(path, "rb") as f:
            content = f.read()
    else:
        content = None

    if content is None:
        if new_content is None:
            raise RuntimeError("File '%s' does not exists!" % path)
        kind = "New file '%s'" % path
        text4user = s(new_content)
    elif new_content is None:
        kind = "Removing file '%s'" % path
        text4user = s(content)
    else:
        kind = "Changing file '%s'" % path
        text4user = "\n".join(unified_diff(
            s(content).splitlines(),
            s(new_content).splitlines()
        ))

    ask = RootCommitDialog(tk, kind, text4user)
    if not ask.wait():
        return

    tmp = join(".", "-".join(path.split(sep)))
    with open(tmp, "wb") as f:
        f.write(new_content)

    try:
        if new_content is None:
            run("sudo", "--askpass", "rm", path)
        else:
            run("sudo", "--askpass", "mv", tmp, path)
    except RuntimeError as e:
        raise SuDoFailed(e)


re_spaces = compile(br"\s")


class Line(object):

    def __init__(self, text):
        self.text = text

    @property
    def words(self):
        return re_spaces.split(self.text)


class AliasAlreadyExists(RuntimeError): pass


class AliasDoesNotExist(ValueError): pass


class NoOptionForDriver(ValueError): pass


class NoValueForDriverOption(ValueError): pass


class LocalConf(object):

    def __init__(self):
        self.reload()

    def reload(self):
        if exists(LOCAL_CONF):
            with open(LOCAL_CONF, "rb") as f:
                before = f.read()
        else:
            before = None

        self.before = before

        if before is None:
            self.lines = [
                Line(b"# This file has been created by %s" % __file__),
                Line(b"# Do not modify"),
                Line(b""),
            ]
        else:
            self.lines = [Line(l.strip()) for l in before.splitlines()]

    @property
    def current(self):
        return b"\n".join(l.text for l in self.lines)

    def has_alias(self, modalias, module):
        for l in self.lines:
            if not l.text.startswith(b"alias"):
                continue
            try:
                ma, mod = l.words[1:3]
            except IndexError:
                continue

            if ma == modalias and mod == module:
                return True
        return False

    def remove_alias(self, modalias, module):
        for idx, l in enumerate(self.lines):
            if not l.text.startswith(b"alias"):
                continue
            try:
                ma, mod = l.words[1:3]
            except IndexError:
                continue

            if ma == modalias and mod == module:
                break
        else:
            raise AliasDoesNotExist("No modalias %s to %s" % (modalias, module))

        del self.lines[idx]

    def add_alias(self, modalias, module):
        content = b"alias %s %s" % (modalias, module)
        last_alias = 0
        for idx, l in enumerate(self.lines, 1):
            if content == l.text:
                raise AliasAlreadyExists("Alias '%s' already exists" % content)
            if l.text.startswith(b"alias"):
                last_alias = idx

        if last_alias == 0:
            self.lines.append(Line(""))
            self.lines.append(Line(content))
        else:
            self.lines.insert(last_alias, Line(content))

    def iter_option_values(self, driver, opt_name):
        for l in self.lines:
            if not l.text.startswith(b"options"):
                continue
            words = l.words
            if words[1] != driver:
                continue
            for opt in words[2:]:
                name, value = opt.split(b"=")
                if name != opt_name:
                    continue
                for v in value.split(b","):
                    yield v

    def has_option_value(self, driver, opt_name, value):
        for v in self.iter_option_values(driver, opt_name):
            if v == value:
                return True
        return False

    def append_option(self, driver, opt_name, *values):
        last_option = 0
        for idx, l in enumerate(self.lines, 1):
            if not l.text.startswith(b"options"):
                continue
            words = l.text.split(b" ")
            cur_drv = words[1]
            if cur_drv != driver:
                continue

            last_option = idx

            for widx, opt in enumerate(words[2:], 2):
                name, value = opt.split(b"=")

                if name == opt_name:
                    cur_vals = value.split(b",")

                    for v in values:
                        if v not in cur_vals:
                            words[widx] += b"," + v

                    break
            else:
                continue

            l.text = b" ".join(words)
            break
        else:
            if last_option == 0:
                content = Line(b"options %s %s=%s" % (
                    driver, opt_name, ",".join(values)
                ))
                self.lines.append(Line(b""))
                self.lines.append(content)
            else:
                self.lines[last_option - 1].text += b" %s=%s" % (
                    opt_name, ",".join(values)
                )

    def remove_option(self, driver, opt_name, *values):
        for idx, l in enumerate(self.lines, 0):
            if not l.text.startswith(b"options"):
                continue
            words = l.text.split(b" ")
            cur_drv = words[1]
            if cur_drv != driver:
                continue

            for widx, opt in enumerate(words[2:], 2):
                name, value = opt.split(b"=")
                if name == opt_name:
                    break
            else:
                continue

            cur_vals = value.split(b",")
            for v in values:
                try:
                    cur_vals.remove(v)
                except ValueError:
                    raise NoValueForDriverOption(
                        "option %s for driver %s has no value %s" % (
                            opt_name, driver, v
                        )
                    )

            if cur_vals:
                words[widx] = name + b"=" + b",".join(cur_vals)
            else:
                del words[widx]

            if len(words) > 2:
                l.text = b" ".join(words)
            else:
                del self.lines[idx]
            break
        else:
            raise NoOptionForDriver("no option %s for driver %s" % (
                opt_name, driver
            ))


local_conf = None


class RunError(RuntimeError):

    def __init__(self, out, err, *a, **kw):
        super(RuntimeError, self).__init__(*a, **kw)
        self.out = out
        self.err = err


def run(*args, **kw):
    command = " ".join(args)
    print(command)
    kw["stderr"] = PIPE
    kw["stdout"] = PIPE
    p = Popen(args, **kw)
    out, err = p.communicate()
    ret = p.returncode
    if ret:
        raise RunError(out, err, "Failed command: " + command)
    return out, err


iid2obj = bidict()


class SysObj(object):

    def __init__(self, iid = None):
        self._iid = None
        self.iid = iid

    @property
    def iid(self):
        return self._iid

    @iid.setter
    def iid(self, iid):
        if iid == self._iid:
            return
        if self._iid is not None:
            del iid2obj[self._iid]
        if iid is not None:
            iid2obj[iid] = self
        self._iid = iid


class IOMMUGroup(SysObj):

    def __init__(self, path, iid = None):
        super(IOMMUGroup, self).__init__(iid = iid)

        self.path = path

    def iter_devices(self):
        return iter(self.devices)

    @lazy
    def number(self):
        return int(split(self.path)[-1])

    def __lt__(self, g):
        if not isinstance(g, IOMMUGroup):
            raise TypeError
        return self.number < g.number

    def __str__(self):
        return "IOMMU Group " + str(self.number)

    @lazy
    def devices(self):
        devs_dir = join(self.path, "devices")

        return tuple(sorted(
            IOMMUDevice(join(devs_dir, d), self) for d in listdir(devs_dir)
        ))


def pci_id(string):
    "Expected string format: word word ... word [id]"
    return string.split(b" ")[-1][1:-1]


class IOMMUDevice(SysObj):

    def __init__(self, path, grp, iid = None):
        super(IOMMUDevice, self).__init__(iid = iid)

        self.addr = split(path)[1]
        self.path = path
        self.grp = grp

    @lazy
    def addr_tuple(self):
        root, bus, dev_fn = self.addr.split(':')
        dev, fn = dev_fn.split('.')
        return tuple(int(x, base = 16) for x in (root, bus, dev, fn))

    @lazy
    def lspci(self):
        out, __ = run("lspci", "-k", "-x", "-vmm", "-nn", "-s", self.addr)
        info = OrderedDict()
        for l in out.splitlines():
            if not l:
                continue
            try:
                k, v = l.split(b":", 1)
            except ValueError:
                print("badly formated line " + l)
                continue
            info[k] = v.strip()

        return info

    @lazy
    def dev_id(self):
        device = self.lspci[b"Device"]
        ret = pci_id(device)
        return ret

    @lazy
    def vendor_id(self):
        vendor = self.lspci[b"Vendor"]
        ret = pci_id(vendor)
        return ret

    @lazy
    def modalias(self):
        with open(
            # https://heiko-sieger.info/blacklisting-graphics-driver/
            join(ROOT, "sys", "bus", "pci", "devices", self.addr, "modalias"),
            "rb"
        ) as modalias:
            return modalias.read().strip()

    @property
    def vfio_modalias(self):
        return local_conf.has_alias(self.modalias, b"vfio-pci")

    @property
    def vfio_assigned(self):
        vid_did = b"%s:%s" % (self.vendor_id, self.dev_id)
        return local_conf.has_option_value(b"vfio-pci", b"ids", vid_did)

    def __lt__(self, dev):
        if not isinstance(dev, IOMMUDevice):
            raise TypeError
        return self.addr_tuple < dev.addr_tuple

    def __str__(self):
        return self.addr


def iid_get_sysobj(tv, iid):
    while iid not in iid2obj:
        iid = tv.parent(iid)
        if not iid:
            raise ValueError("Foreign item id %s" % iid)
    return iid2obj[iid]


def co_main(cfg, tk, tv):
    if cfg.geometry:
        tk.geometry(cfg.geometry)
        yield

    grps = sorted(
        IOMMUGroup(join(IOMMU_GROUPS, g)) for g in listdir(IOMMU_GROUPS)
    )

    for grp in grps:
        giid = tv.insert("", END, text = grp, open = True)
        grp.iid = giid

        for dev in grp.devices:
            dev.iid = tv.insert(giid, END, text = dev, open = True)

    yield

    for dev in iid2obj.values():
        if not isinstance(dev, IOMMUDevice):
            continue
        yield

        for k, v in dev.lspci.items():
            iid = tv.insert(dev.iid, END, text = k, values = (s(v),))
            assert dev is iid_get_sysobj(tv, iid)

        yield
        tv.insert(dev.iid, END, text = "modalias", values = (s(dev.modalias),))
        dev.vfio_modalias_iid = tv.insert(dev.iid, END,
            text = "VFIO mod-aliasing",
            values = (dev.vfio_modalias,)
        )
        yield
        dev.vfio_assigned_iid = tv.insert(dev.iid, END,
            text = "VFIO assigned",
            values = (dev.vfio_assigned,)
        )

    yield

    reload_disable_vga()

    yield

    if cfg.tv_col_width:
        for iid, width in cfg.tv_col_width.items():
            tv.column(iid, width = width)


class IOMMUTV(Treeview, TkPopupHelper):

    def __init__(self, *a, **kw):
        Treeview.__init__(self, *a, **kw)
        TkPopupHelper.__init__(self)

        self.tv_popup_IOMMUDevice = Menu(self, tearoff = False)
        self.tv_popup_IOMMUDevice.add_command(
            label = "Add vfio-pci modalias",
            command = self.add_vfio_pci_modalias
        )
        self.tv_popup_IOMMUDevice.add_command(
            label = "Remove vfio-pci modalias",
            command = self.remove_vfio_pci_modalias
        )

        self.bind("<Button-3>", self.on_tv_b3, "+")

    def add_vfio_pci_modalias(self):
        dev = self.current_popup_tag

        try:
            local_conf.add_alias(dev.modalias, b"vfio-pci")
        except AliasAlreadyExists:
            return

        local_conf.append_option(
            b"vfio-pci", b"ids", dev.vendor_id + b":" + dev.dev_id
        )

        self.modalias_commit(dev)

    def modalias_commit(self, dev):
        try:
            root_commit(self, LOCAL_CONF, local_conf.current)
        except SuDoFailed:
            # something vent wrong on lower level
            print_exc()

        local_conf.reload()
        self.item(dev.vfio_modalias_iid, values = (dev.vfio_modalias,))
        self.item(dev.vfio_assigned_iid, values = (dev.vfio_assigned,))

    def remove_vfio_pci_modalias(self):
        dev = self.current_popup_tag

        try:
            local_conf.remove_alias(dev.modalias, b"vfio-pci")
        except AliasDoesNotExist:
            return

        try:
            try:
                local_conf.remove_option(
                     b"vfio-pci", b"ids", dev.vendor_id + b":" + dev.dev_id
                )
            except:
                local_conf.reload()
                raise
        except NoOptionForDriver:
            return
        except NoValueForDriverOption:
            # Somebody hacked local.conf?
            print_exc()
            return

        self.modalias_commit(dev)

    def on_tv_b3(self, e):
        row = self.identify_row(e.y)

        if row != "":
            self.selection_set(row)

        obj = iid_get_sysobj(self, row)

        try:
            popup = getattr(self, "tv_popup_" + type(obj).__name__)
        except AttributeError:
            return

        self.show_popup(e.x_root, e.y_root, popup, obj)


def update_initramfs():
    try:
        out, err = run("sudo", "--askpass", "update-initramfs", "-u")
    except RunError as e:
        print_exc()
        out, err = e.out, e.err

    print("out:\n%s\nerr:\n%s\n" % (out, err))


def disable_vga_handler(*__):
    if disable_vga_var.get():
        if local_conf.has_option_value(b"vfio-pci", b"disable_vga", b"1"):
            return
        local_conf.append_option(b"vfio-pci", b"disable_vga", b"1")
    else:
        if not local_conf.has_option_value(b"vfio-pci", b"disable_vga", b"1"):
            return
        local_conf.remove_option(b"vfio-pci", b"disable_vga", b"1")

    try:
        root_commit(disable_vga_var._root, LOCAL_CONF, local_conf.current)
    except SuDoFailed:
        # something vent wrong on lower level
        print_exc()

    disable_vga_var._root.after(1, reload_disable_vga)


def reload_disable_vga():
    local_conf.reload()

    disable_vga_var.set(
        local_conf.has_option_value(b"vfio-pci", b"disable_vga", b"1")
    )


def askpass(argv):
    root = Tk()
    root.title("Password required")

    Label(root, text = argv[1]).pack()
    var = StringVar(root)
    e = Entry(root, show="*", textvariable = var, width = 30)
    e.pack(fill = "x", expand = True)
    e.focus_set()

    root._entered = False

    def on_return(*__):
        root._entered = True
        root.destroy()

    e.bind("<Return>", on_return)
    e.bind("<Escape>", lambda *__: root.destroy())

    root.mainloop()

    if root._entered:
        print(var.get())


def main():
    if len(argv) > 1 and "[sudo]" in argv[1]:
        askpass(argv)
        return

    environ["SUDO_ASKPASS"] = __file__

    global local_conf
    global disable_vga_var

    local_conf = LocalConf()

    tk = Tk()
    tk.title("IOMMU Info")

    tk.rowconfigure(0, weight = 0)
    buttons = Frame(tk)
    buttons.grid(row = 0, column = 0, columnspan = 2, sticky = "EWS")

    Button(buttons, text = "Update initramfs", command = update_initramfs).\
        pack(side = RIGHT)

    disable_vga_var = BooleanVar(tk)
    disable_vga_var.trace_variable("w", disable_vga_handler)
    Checkbutton(buttons,
        text = "VFIO disable_vga",
        variable = disable_vga_var
    ).pack(side = LEFT)

    tk.rowconfigure(1, weight = 1)
    tk.columnconfigure(0, weight = 1)

    tv = IOMMUTV(tk, columns = ("i",))
    tv.grid(row = 1, column = 0, sticky = "NESW")

    add_scrollbars_native(tk, tv, row = 1)

    Sizegrip(tk).grid(row = 2, column = 1, sticky = "ES")

    tv.heading("i", text = "Information")

    for c in ("#0",) + tv.cget("columns"):
        tv.column(c, stretch = False)

    with Persistent(expanduser(join("~",".qdt.iommu.py")),
        geometry = None,
        tv_col_width = None
    ) as cfg:
        task = co_main(cfg, tk, tv)

        stack = [task]

        def after_func():
            try:
                cur = stack[-1]
            except IndexError:
                print("no more tasks")
                return

            try:
                ret = next(cur)
            except StopIteration:
                print("return from " + cur.__name__)
                stack.pop()
            else:
                if type(ret) is GeneratorType:
                    print("call " + ret.__name__)
                    stack.append(ret)

            tk.after(10, after_func)

        tk.after(1, after_func)

        def on_destroy():
            cfg.geometry = tk.geometry().split("+", 1)[0]
            cols = tv.cget("columns")
            cfg.tv_col_width = dict(
                (col, tv.column(col, "width")) for col in cols
            )
            tk.destroy()

        tk.protocol("WM_DELETE_WINDOW", on_destroy)

        tk.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
