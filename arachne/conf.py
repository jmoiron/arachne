#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Configuration helpers."""

from arachne.utils import Registry

def merge(*dicts):
    """Merge dictionaries in order, with the final one taking precedence."""
    d = {}
    for dict in dicts:
        d.update(dict)
    return d

def require(cls, conf, keys):
    """Check that required keys are there for a class."""
    cls = cls.__class__
    for k in keys:
        if k not in conf:
            msg = "Required config value \"%s\" unavailable for %s.%s"
            raise Exception(msg % (k, cls.__module__, cls.__name__))

class Settings(Registry):
    def view(self, string):
        return dict([(k,v) for k,v in self.items() if string.lower() in k.lower()])

    def like(self, string):
        return dict([(k.split('_', 1)[1], v) for k,v in self.items() if string.lower() in k.lower()])

defaults = {
    'port': 5000,
}

settings = Settings()
settings.update(defaults)

