"""
Python 3.14 makes super() copyable; Django's BaseContext.__copy__ used copy(super()),
which breaks template/admin rendering. Upstream fixed this in newer releases; this
patch applies the same strategy for Django 4.2.x on 3.14+.
"""
from __future__ import annotations

import sys
from copy import copy as lib_copy


def apply() -> None:
    if sys.version_info < (3, 14):
        return
    if getattr(apply, "_done", False):
        return

    from django.template import context as ctx_mod

    def __copy__(self):
        duplicate = ctx_mod.BaseContext()
        duplicate.__class__ = self.__class__
        duplicate.__dict__ = lib_copy(self.__dict__)
        duplicate.dicts = self.dicts[:]
        return duplicate

    ctx_mod.BaseContext.__copy__ = __copy__
    apply._done = True  # type: ignore[attr-defined]
