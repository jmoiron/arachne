#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrapper around umemcache which automatically manages distinct connections
per greenlet."""

import umemcache
import gevent

from arachne.conf import settings, merge, require
from arachne.utils import encode, decode

defaults = {
    "port": 11211,
}

class Memcached(object):
    def __init__(self, **kw):
        config = merge(defaults, settings.like("memcached"), kw)
        require(self, config, ("host", "port"))
        self.config = config
        self.pool = {}

    def client(self):
        current = gevent.getcurrent()
        if current in self.pool:
            return self.pool[current]
        c = self.config
        con = umemcache.Client("%s:%s" % (c['host'], c['port']))
        con.connect()
        self.pool[current] = con
        return con

    def add(self, key, value):
        self.client().add(key, value)

    def get(self, key):
        ret = self.client().get(key)
        return ret[0] if ret else ret

    def set(self, key, data, *a):
        self.client().set(key, data, *a)

    def incr(self, key, *a):
        self.client().incr(key, *a)

    def decr(self, key, *a):
        self.client().decr(key, *a)

    def get_multi(self, *keys):
        d = self.client().get_multi(keys)
        return dict([(k,v[0]) for k,v in d.iteritems()])

    def version(self):
        return self.client().version()

    def stats(self):
        return self.client().stats()

