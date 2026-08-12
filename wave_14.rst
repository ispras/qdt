Wave 14
=======

.. workflow:: MR
   :tags: MR, feature, bug, ASAP
   :branch: wave_14
   :assignee: bda

Many simple commits from ``devel``, including bug fixes and Python
compatibility updates.

First patches are fixes mostly.

Next patches do touch different things of the project.

There are many patches to ``source.function.tree`` model at the end.
This is not a refactoring only.
It's on the way to ``pygen`` compatibility
(more patches are in ``devel`` yet).
A function body description is to be able to dump to a Python script.

v2
--

v1.1 fixes are moved near to targets

fixed typo "though\ **t**" ("th\ **r**ough") in commit messages

``"define `prior`ity at `class` level"`` commit series is removed

``OpAssign``, ``OpDeclareAssign``, ``OpCombAssign`` priority is increased (14)

fixed typo ``iter_base_complet_type_names`` to
 ``iter_base_complet``**e**``_type_names``

``common/os_wrappers.py``: ``import``s from ``os`` are merged
