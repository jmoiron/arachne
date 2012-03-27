#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""cassandra support for unwound spider using pycassa"""

import pycassa

from arachne import utils
from arachne.conf import settings, merge, require

defaults = {
    'port': 9160,
    'timeout': 5,
    'max_retries': 10,
    'pool_timeout': 60,
    'recycle': 1000,
    'prefill': False,
}

encode = utils.encode

def decode(data, colname=None):
    """Decode data coming out of storage."""
    if colname:
        return utils.decode(data[colname])
    return utils.decode(data)


class Cassandra(object):
    def __init__(self, **kwargs):
        config = merge(defaults, settings.like('cassandra'), kwargs)
        require(self, config, ('cf_content', 'keyspace', 'servers', 'port'))
        self.__dict__.update(config)
        self.pool_size = len(self.servers) * 2
        self.pool = pycassa.ConnectionPool(
            self.keyspace,
            self.servers,
            timeout=self.timeout,
            max_retries=self.max_retries,
            pool_timeout=self.pool_timeout,
            pool_size=self.pool_size,
            recycle=self.recycle,
            prefill=self.prefill,
        )
        self.client = pycassa.ColumnFamily(self.pool, self.cf_content)

    def set(self, user_id, data, uuid=None):
        return self.client.insert(str(user_id), {uuid: encode(data)})

    def get(self, user_id, uuid):
        return decode(self.client.get(str(user_id), columns=[uuid]).values()[0])

