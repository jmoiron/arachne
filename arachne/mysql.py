#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Wrapper around umysql which automatically manages distinct connections
per greenlet."""

import umysql
import gevent

from arachne.utils import ConnectionPool
from arachne.conf import settings, merge, require

defaults = {
    "port": 3306,
}

class MysqlConnectionPool(ConnectionPool):
    def __init__(self, config, maxsize=10):
        maxsize = int(config.get("poolsize", maxsize))
        super(MysqlConnectionPool, self).__init__(maxsize)
        self.config = config

    def connection(self):
        c = self.config
        con = umysql.Connection()
        con.connect(c['host'], c['port'], c['username'], c['password'], c['database'])
        return con

class Mysql(object):
    def __init__(self, **kw):
        config = merge(defaults, settings.like("mysql"), kw)
        require(self, config, ("host", "password", "username", "database"))
        self.config = config
        self.pool = MysqlConnectionPool(config)

    def query(self, sql, args=None):
        """Return the results for a query."""
        c = self.pool.get()
        try:
            if args:
                return c.query(sql, args)
            return c.query(sql)
        finally:
            self.pool.put(c)

    def getone(self, sql, args=None):
        return self.query(sql, args)[0]

    def dquery(self, sql, args=None):
        """Return a list of dictionaries instead of tuples from a query."""
        results = self.query(sql, args)
        fields = [f[0] for f in results.fields]
        return [dict(zip(fields, row)) for row in results.rows]

    def dgetone(self, sql, args=None):
        return self.dquery(sql, args)[0]

