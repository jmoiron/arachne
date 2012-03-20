#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrapper around umysql which automatically manages distinct connections
per greenlet."""

import umysql
import gevent

from arachne.conf import settings, merge, require

defaults = {
    "port": 3306,
}

class Mysql(object):
    def __init__(self, **kw):
        config = merge(defaults, settings.like("mysql"), kw)
        require(self, config, ("host", "password", "username", "database"))
        self.config = config
        self.pool = {}

    def client(self):
        current = gevent.getcurrent()
        if current in self.pool:
            return self.pool[current]
        c = self.config
        con = umysql.Connection()
        con.connect(c['host'], c['port'], c['username'], c['password'], c['database'])
        self.pool[current] = con
        return con

    def query(self, sql, args=None):
        c = self.client()
        if args:
            return c.query(sql, args)
        return c.query(sql)

    def dquery(self, sql, args=None):
        """Return a list of dictionaries instead of tuples from a query."""
        results = self.query(sql, args)
        fields = [f[0] for f in results.fields]
        return [dict(zip(fields, row)) for row in results.rows]

