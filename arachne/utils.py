#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Generally useful utilities."""

import re
import inspect
import time
import zlib
import ujson as json
import logging
from functools import wraps
from collections import defaultdict

class Registry(defaultdict):
    """An OpenStruct-like registry."""
    def __getattr__(self, name):
        if name in self: return self[name]
        return None
    def __setattr__(self, name, val):
        self[name] = val

def argspec(function, ignore_self=True):
    """Returns a properly formatted argspec for a function.  If ignore_self is
    True, then a 'self' arg is thrown away.  The return value is meant to look
    like the function definition."""
    spec = inspect.getargspec(function)
    if 'self' in spec[0]:
        spec = (spec[0][1:], spec[1], spec[2], spec[3])
    return '%s%s' % (function.__name__, inspect.formatargspec(*spec))

ntb_re = re.compile(r'\r\n|\r|\n')
def newline_to_br(text):
    return ntb_re.sub('<br>', text)

def keygetter(key, default=None):
    def getkey(obj):
        return obj.get(key, default)
    return getkey

def encode(obj):
    """Encode data for insertion into storage."""
    return zlib.compress(json.dumps(obj))

def decode(data):
    """Decode data coming out of storage."""
    return json.loads(zlib.decompress(data))

from Queue import Queue
import contextlib

class ConnectionPool(object):
    """A simple connection pool which uses a queue to limit how many
    connections to a single resource are made.  Override the `connection`
    method to make new connections to your resource."""
    def __init__(self, maxsize=10):
        self.maxsize = maxsize
        self.pool = Queue()
        self.size = 0

    def get(self):
        pool = self.pool
        if self.size >= self.maxsize or pool.qsize():
            return pool.get()
        self.size += 1
        try:
            con = self.new_connection()
        except:
            self.size -= 1
            raise
        return con

    def put(self, con):
        self.pool.put(con)

    @contextlib.contextmanager
    def connection(self):
        con = self.get()
        try:
            yield con
        finally:
            self.put(con)

    def new_connection(self, *a, **kw):
        raise NotImplementedError


from heapq import heappush, heappop, heapify, heapreplace

class Heap(object):
    """Heap class using heapq library."""
    def __init__(self, items=None):
        self.items = items or []
        heapify(self.items)

    def pop(self):
        return heappop(self.items)

    def push(self, item):
        return heappush(self.items, item)

    def replace(self, item):
        return heapreplace(self.items, item)

    def __getitem__(self, item):
        return self.items[item]

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

def timer(f, threshold=0.5):
    """Simple timing of a whole function.  Does not take into consideration time
    this greenlet has spent sleeping."""
    logger = logging.getLogger("%s.%s" % (f.__module__, f.__name__))
    @wraps(f)
    def wrapper(*a, **kw):
        t0 = time.time()
        r = f(*a,**kw)
        td = time.time() - t0
        if td > threshold:
            logger.info("took %0.2fs (threshold: %0.2f)" % (td, threshold))
        return r
    return wrapper

class Stopwatch(object):
    """A timer that allows you to make named ticks and can print a simple
    breakdown of the time between ticks after it's stopped."""
    def __init__(self, name='Stopwatch'):
        self.name = name
        self.start = time.time()
        self.ticks = []

    def tick(self, name):
        self.ticks.append((name, time.time()))

    def stop(self):
        self.stop = time.time()

    def summary(self):
        """Return a summary of timing information."""
        self.stop()
        total = self.stop - self.start
        s = "%s duration: %0.2f\n" % (self.name, total)
        prev = ("start", self.start)
        for tick in self.ticks:
            s += ("   %s => %s" % (prev[0], tick[0])).ljust(30) + "... %0.2fs\n" % (tick[1] - prev[1])
            prev = tick
        s += ("   %s => end" % (tick[0])).ljust(30) + "... %0.2fs" % (self.stop - tick[1])
        return s

