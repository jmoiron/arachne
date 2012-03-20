#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrapper around umemcache which automatically manages distinct connections
per greenlet."""

import umemcache
import gevent

from arachne.conf import settings, merge, require

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

    def get(self, key, *default):
        ret = self.client().get(key)
        if ret is None and default:
            return default[0]
        return ret

    def set(self, key, data, *a):
        self.client().set(key, data, *a)

    def incr(self, key, *a):
        self.client().incr(key, *a)

    def decr(self, key):
        self.client().decr(key, *a)

    def version(self):
        return self.client().version()

    def stats(self):
        return self.client().stats()

