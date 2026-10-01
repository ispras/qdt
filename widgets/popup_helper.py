__all__ = [
    "TkPopupHelper"
]

from six.moves.tkinter import (
    Misc,
    TclError,
)


class DoShow(BaseException):
    def __init__(self, show):
        self.show = show

class TkPopupHelper(Misc):

    def __init__(self):
        print("TkPopupHelper.__init__ call is not required anymore")

    def __init_popup_helper(self):
        self.__init_popup_helper = lambda : None
        toplevel = self.winfo_toplevel()
        if toplevel is not None:
            toplevel.bind("<Button-1>", self.__hide_on_mouse, "+")

    def __hide_on_mouse(self, event):
        self.hide_popup()

    current_popup = None
    current_popup_tag = None

    def tk_popup_helper_cleanup(self):
        self.current_popup = None
        self.current_popup_tag = None

    def notify_popup_command(self):
        """The method notify_popup_command should be called during any popup
menu command callback to cleanup the helper internal attributes.
        """
        self.tk_popup_helper_cleanup()

    def show_popup(self, x, y, popup, tag = None):
        """Shows given menu (popup).
@param tag:
    Sometimes one instance of the menu is used for a set of similar essences.
Then posting the menu for one of they twice should result in menu unposting.
Else showing it for another one should show unpost previous menu and post new
(at new position likely). The tag argument is used to identify the essence.
It could be any object reference unique for the essence with respect to "!="
operator (except None)
        """
        self.__init_popup_helper()

        # Do not show same menu again. Just hide it.
        try:
            if self.current_popup is None:
                # no menu is shown now
                raise DoShow(True)
            else:
                # unpost current menu
                self.current_popup.unpost()

            if popup is not self.current_popup:
                # popup is another menu
                raise DoShow(True)

            # popup is same menu
            if self.current_popup_tag is not None:
                if tag != self.current_popup_tag:
                    # menu is for other tag
                    raise DoShow(True)

        except DoShow as e:
            show = e.show
        else:
            # do not show menu by default
            show = False
        finally:
            # the value is not more needed
            self.current_popup = None

        if show:
            self.current_popup_tag = tag
            try:
                try:
                    # Save popup coordinates manually because tk_popup behaves
                    # differently on Unix and on Windows
                    # See: https://core.tcl-lang.org/tk/tktview?name=585003ffff
                    self.popup_x, self.popup_y = x, y
                    popup.tk_popup(x, y)
                except TclError as e:
                    """ If Shift is held then an error raised with message:
'grab failed: another application has grab'. The menu is known to work this
case. So, hide this error.
                    """
                    """ XXX: It's likely that the string is not localized and
                    will remain constant. """
                    if not str(e).startswith("grab failed"):
                        raise e
            except:
                print("Cannot show popup!")
                # ensure that the menu remains hidden
                try:
                    popup.unpost()
                except:
                    pass
            else:
                self.current_popup = popup
            finally:
                popup.grab_release()
        else:
            self.current_popup_tag = None

    def hide_popup(self):
        if self.current_popup:
            self.current_popup.unpost()
            self.tk_popup_helper_cleanup()
