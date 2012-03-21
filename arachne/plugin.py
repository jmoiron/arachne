#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Plugin support."""

import inspect
from itertools import chain
from types import FunctionType, MethodType
from arachne.utils import Registry

class PluginRegistry(Registry):
    """Registry that allows for some distinct features."""
    aliases = {}

    def by_path(self, path):
        if path in self.aliases:
            return self.aliases[path]
        plugin, method = path.split('/')
        if plugin in self and method in self[plugin].methods:
            return self[plugin].methods[method]
        return None

    def alias(self, name, path):
        """Alias a new name, which is a path, to an existing path."""
        self.aliases[name] = self.by_path(path)

registry = PluginRegistry()

hourly = 3600
daily = 86400
half_hourly = 1600

is_method = lambda m: isinstance(m, (FunctionType, MethodType))

def argument_alias(method, args):
    """Apply argument aliases for a method.  These aliases are stored on
    the plugin and are additive to the args.  Args are modified in place but
    also returned."""
    plugin = method.im_self
    if not hasattr(plugin, 'aliases'):
        return args
    for k,v in plugin.aliases.iteritems():
        args[k] = args[v]
    return args

def interval(seconds, **kw):
    """Mark a methods interval individually.  You can also pass any other
    keys you want the function to be marked with, ex. for richer QOS interval
    concepts or any extra data you might want."""
    def wrapper(func):
        func.interval = seconds
        for key,value in kw:
            setattr(func, key, value)
        if kw: func._extras = kw
        return func
    return wrapper

class Plugin(object):
    """A simple plugin object, which is a wrapper that allows various things to
    be introspected at runtime."""
    def __init__(self):
        self.plugin_name = self.__class__.__name__.lower()
        self.methods = self._methods()
        registry[self.plugin_name] = self

    def _methods(self):
        """Determine which methods on this plugin are exposed."""
        default_interval = getattr(self, 'default_interval', hourly)
        classdict = self.__class__.__dict__
        exposed = {}
        for name,member in inspect.getmembers(self):
            if is_method(member) and not name.startswith('_'):
                method = classdict[name]
                method.exposed = True
                method.interval = getattr(method, 'interval', default_interval)
                exposed[name] = member
        return exposed

