#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""AMQP adapters for the scheduler."""

from functools import wraps
from gevent import queue, sleep
from time import time

from arachne.conf import settings, merge, require
from kombu.transport.amqplib import Connection, amqp

defaults = {
    "port": 5672,
    "prefetch_count": 50,
    "queue_size": 100,
}

def autoreconnect(func):
    @wraps(func)
    def wrapper(self, *a, **kw):
        try:
            ret = func(self, *a, **kw)
        except:
            self.reconnect()
            ret = func(self, *a, **kw)
        return ret
    return wrapper

class Amqp(object):
    def __init__(self, **kw):
        config = merge(defaults, settings.like("amqp"), kw)
        required = ("port", "username", "password", "host", "vhost", "exchange", "queue")
        require(self, config, required)
        self.__dict__.update(config)
        self.config = config
        self.reconnect()

    def reconnect(self):
        self.connection = Connection(
            host=self.host,
            virtual_host=self.vhost,
            userid=self.username,
            password=self.password
        )
        qa = dict(durable=False, auto_delete=False)
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue,exclusive=False, **qa)
        self.channel.exchange_declare(self.exchange, type="fanout", **qa)
        self.channel.queue_bind(queue=self.queue, exchange=self.exchange)

    @autoreconnect
    def status(self, cached=True):
        status = self.channel.queue_declare(queue=self.queue, exclusive=False,
                durable=False, auto_delete=False)
        name, message_count, consumer_count = status
        return dict(name=status[0], messages=status[1], consumers=status[2])

    @autoreconnect
    def publish(self, message, queue=None):
        self.channel.basic_publish(amqp.Message(message), queue or self.queue)

    @autoreconnect
    def get(self, queue=None):
        """Attempt to get something from a queue.  If queue is None, uses the
        default queue for this client."""
        m = self.channel.basic_get(queue or self.queue)
        if m is not None:
            self.channel.basic_ack(m.delivery_tag)
        return m

    def poll(self, queue=None, timeout=None, every=0.1):
        """Poll every `every` seconds for a message on queue."""
        start = time()
        m = self.get(queue)
        while m is None:
            sleep(every)
            now = time()
            if timeout and now - start >= timeout:
                return m
            m = self.get(queue)
        return m

# FIXME: a joinable queue?
class Queue(queue.Queue):

    def fill(self, client, queue=None):
        """Fill a local gevent-synced queue with items from a client."""
        # FIXME: write this


