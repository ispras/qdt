__all__ = [
    "ObjectVisitor"
  , "SkipVisiting"
  , "StopVisiting"
  , "VisitingIsNotImplemented"
]


# Not an `Exception`. It's (ab)using of `try` logic.
class SkipVisiting(BaseException):
    pass

# Not an `Exception` too...
class StopVisiting(BaseException):
    pass


class VisitingIsNotImplemented(NotImplementedError):
    pass


class ObjectVisitor(object):
    """ The class defines common interface to traverse an object tree.

A tree is defined by an attribute with customizable name.
The attribute should be able to return an iterable of strings.
Each string is name of another attribute which contains reference to an
object to traverse next.

The iterable attribute name is "__visitable__" by default.
An example of the iterable attribute type is `list`.
The name of the attribute can be customized by `field_name` argument of
base constructor.

To traverse an object tree set `root`, argument of `__init__`, to the root
object and call `visit`.

Each time an object is visited the `on_visit` and `on_leave` methods are
called.
Neither `on_visit` nor `on_leave` is called for the root.
`on_visit` is called before subtree visiting and `on_leave` is called after it.
A reference the object being visited is stored in `self.cur`.
That reference and the name (index, key, attribute, ...) inside the parent of
the current object are also stored in the last entry of `self.path`.


Default `on_visit` (`on_leave`) does nothing.
The user should override it to define needed behaviour.

To prevent traversing of subtree the `on_visit` can raise `SkipVisiting`.
`on_leave` is called even if `SkipVisiting` was raised.
To stop traversing at all `on_visit` can raise `StopVisiting`.
`on_leave` is called foreach node `on_visit` was called for.

The `replace` could be called to replace current object in its parent.
Note that `replace` method raises `SkipVisiting` by default.

Features (+) implemented, (-) TODO:
 - detection for cycles
 + visiting of simple reference to object
 + replacing of reference
 + visiting of references in list
 + replacement of reference in list
 + visiting of references in dictionary
 + replacement of references (values) in dictionary
 + visiting of references in set
 + replacement of reference in set
 + visiting of references in tuple
 - replacement of reference in tuple (new tuple should be constructed
   because the tuple class does not support editing)
 - recursive visiting of tuples, lists, dictionaries
 - replacement during recursive visiting of tuple
 - replacement during recursive visiting of list
 - replacement during recursive visiting of dictionary

    """
    def __init__(self, root, field_name = "__visitable__"):
        self.path = [(root,)]
        self.cur = root
        self.field_name = field_name

    @property
    def container(self):
        "Container of `cur`rent object"
        return self.path[-2][0]

    @property
    def name(self):
        "Identifier of `cur`rent object in `container`"
        return self.path[-1][1]

    def on_visit(self):
        "default method does nothing"

    def on_leave(self):
        "default method does nothing"

    def replace(self, new_value, skip_trunk = True):
        """ Replaces current (being replaced) node within its container with.

    :param skip_trunk:
        Skip subtree of `new_value` by raising `SkipVisiting` (no return).
        Subtree of previous value will be skipped because of replacement.
        Keep in mind that setting the argument to `False` may quite easy
        lead to fall into a dead loop.
        """

        cur_container = self.container
        cur_name = self.name

        if isinstance(cur_container, (list, dict)):
            cur_container[cur_name] = new_value
        elif isinstance(cur_container, set):
            cur_value = self.path[-1][0]
            cur_container.remove(cur_value)
            cur_container.add(new_value)
        elif isinstance(cur_container, object):
            setattr(cur_container, cur_name, new_value)
        else:
            raise Exception("Replacement for type %s is not implemented" %
                type(cur_container).__name__
            )

        self.path[-1] = (new_value, cur_name)
        self.cur = new_value

        # print self.path_str() + " <- " + str(new_value) 

        if skip_trunk:
            raise SkipVisiting()

    def path_str(self):
        return ".".join(str(n) + "{%s}" % str(o) for o, n in self.path[1:])

    @property
    def previous(self):
        "Iterates objects visited before the current."

        for obj in self.path[:-1]:
            yield obj[0]

    @property
    def root(self):
        return self.path[0][0]

    def _push(self, destination, path_name):
        self.path.append((destination, path_name))
        self.cur = destination

    def _pop(self):
        self.path.pop()
        self.cur = self.path[-1][0]

    def _visit_fields(self, obj):
        try:
            visitable_list = getattr(obj, self.field_name)
        except AttributeError:
            pass
        else:
            for attribute_name in visitable_list:
                attr = getattr(obj, attribute_name)
                self._push(attr, attribute_name)
                try:
                    self._visit(attr)
                except StopVisiting:
                    # TODO: try to move `_pop` to `finally` block, below too
                    self._pop()
                    raise
                self._pop()

    def visit(self):
        try:
            self._visit_items(self.cur)
        except StopVisiting:
            pass
        return self # for call chaining

    def _visit_items(self, attr):
        if isinstance(attr, (list, tuple)):
            self._visit_list(attr)
        elif isinstance(attr, dict):
            self._visit_dict(attr)
        elif isinstance(attr, set):
            self._visit_set(attr)
        elif isinstance(attr, object):
            self._visit_fields(attr)
        else:
            raise VisitingIsNotImplemented(
                "Visiting of attribute '%s' of type '%s is not implemented" % (
                    self.path[-1][1], type(attr).name
                )
            )

    def _visit(self, attr):
        try:
            self.on_visit()
        except SkipVisiting:
            return
        except StopVisiting:
            raise
        else:
            self._visit_items(attr)
        finally:
            self.on_leave()

    def _visit_set(self, attr):
        for e in sorted(attr):
            self._push(e, None) # objects in a set are not named.
            try:
                self._visit(e)
            except StopVisiting:
                self._pop()
                raise
            self._pop()

    def _visit_list(self, attr):
        for i, e in enumerate(attr):
            self._push(e, i)
            try:
                self._visit(e)
            except StopVisiting:
                self._pop()
                raise
            self._pop()

    def _visit_dict(self, attr):
        for k, e in sorted(attr.items()):
            self._push(e, k)
            try:
                self._visit(e)
            except StopVisiting:
                self._pop()
                raise
            self._pop()
