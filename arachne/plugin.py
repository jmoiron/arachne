#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Plugin support."""

import inspect
from types import FunctionType, MethodType
from arachne.utils import Registry

registry = Registry()

hourly = 3600
half_hourly = 1600
every_n_hours = lambda n: n*hourly


def expose(method, interval=hourly):
    """Mark a method as exposed, callable from various interfaces."""
    method.exposed = True
    method.interval = interval
    return method

class Plugin(object):
    """A simple plugin object, which is a wrapper that allows various things to
    be introspected at runtime."""
    def __init__(self):
        self.plugin_name = self.__class__.__name__.lower()
        self._expose()
        self.methods = self._methods()
        registry[self.plugin_name] = self

    def _expose(self):
        """Allow a list of exposed method names to be set in the classes
        "exposed" attribute, utilizing either the default expose interval or
        a default provided by the class in the "interval" attr."""
        if not getattr(self, 'exposed'): return
        interval = getattr(self, 'interval', hourly)
        for method in self.exposed:
            clsdict = self.__class__.__dict__
            expose(clsdict[method], interval)

    def _methods(self):
        """Determine which methods on this plugin are exposed."""
        members = inspect.getmembers(self)
        is_method = lambda m: isinstance(m, (FunctionType, MethodType)) \
                and getattr(m, 'exposed', False)
        return dict([(name,m) for name,m in members if is_method(m)])

