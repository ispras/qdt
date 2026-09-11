Refactoring of `ObjectVisitor`
==============================

.. workflow:: MR
   :tags: MR
   :branch: refactor_visitors
   :assignee: bda

This commit sequence

* fixes naming of ``ObjectVisitor``'s,
* removes ``VisitingIsNotImplemented``,
* introduces ``ObjectVisitor.__field_name__``, a class variable,
* makes small updates to related code.
