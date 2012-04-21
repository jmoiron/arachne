#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""AMQP adapters for the scheduler."""

from functools import wraps
import logging
from gevent import queue, sleep, getcurrent
from time import time

from arachne.conf import settings, merge, require
from arachne.utils import ConnectionPool
from kombu.transport.amqplib import Connection, amqp

defaults = {
    "port": 5672,
    "prefetch_count": 20,
    "queue_size": 100,
    "poolsize": 5,
}

logger = logging.getLogger(__name__)

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

class AmqpConnectionPool(ConnectionPool):
    def __init__(self, config, maxsize=10):
        maxsize = int(config.get("poolsize", maxsize))
        super(AmqpConnectionPool, self).__init__(maxsize)
        self.config = config

    def new_connection(self):
        c = self.config
        con = AmqpClient(**c)
        return con

class AmqpPool(object):
    """A pooled Amqp client.  Multiple connections are made and passed out
    on demand, so they cannot be used by two different greenlets at once.  It
    might be better to use a single amqp connection with a Consumer."""
    def __init__(self, **kw):
        config = merge(defaults, settings.like("amqp"), kw)
        required = ("port", "username", "password", "host", "vhost", "exchange", "queue")
        require(self, config, required)
        self.__dict__.update(config)
        self.config = config
        self.pool = AmqpConnectionPool(config)

    def reconnect(self):
        with self.pool.connection() as client:
            return client.reconnect()

    def status(self, **kw):
        with self.pool.connection() as client:
            return client.status(**kw)

    def publish(self, *a, **kw):
        with self.pool.connection() as client:
            return client.publish(*a, **kw)

    def get(self, *a, **kw):
        with self.pool.connection() as client:
            return client.get(*a, **kw)

    def poll(self, *a, **kw):
        with self.pool.connection() as client:
            return client.poll(*a, **kw)

    def consume(self, *a, **kw):
        with self.pool.connection() as client:
            return client.consume(*a, **kw)

    def cancel(self, *a, **kw):
        with self.pool.connection() as client:
            return client.cancel(*a, **kw)

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
        self.channel.basic_qos(0, self.prefetch_count, False)
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
    def publish(self, message, exchange=None):
        self.channel.basic_publish(amqp.Message(message), exchange or self.exchange)

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

    def consume(self, callback, queue=None, no_ack=True):
        """Start consuming messages from a channel.  Returns the channel.
        Use AmqpClient.cancel() to cancel this consuming."""
        self.tag = self.channel.basic_consume(queue or self.queue, callback=callback, no_ack=no_ack)
        return self.channel

    def cancel(self, tag=None):
        """Cancel consuming."""
        self.channel.basic_cancel(tag or self.tag)

class Consumer(object):
    """A queue consumer.  This queue will consume a channel and fill up a local
    synchronized queue which can then be polled by many greenlets.  The consume
    should be much lower impact than issuing a storm of failing gets."""
    def __init__(self, client=None, size=100):
        self.greenlets = []
        self.messages = queue.Queue(int(size))
        self.client = client if client else Amqp()

    def start(self):
        channel = self.client.consume(callback=self.fill)
        while 1:
            try:
                channel.wait()
            except Exception, e:
                self.client.cancel()
                logger.error("Error occured while waiting on channel: %s" % e)
                self.client.reconnect()
                channel = self.client.consume(callback=self.fill)
        logger.error("leaving impossible-to-leave loop")

    def stop(self):
        logger.debug("Stopping consumer")
        self.client.cancel()

    def fill(self, message):
        """Fill a local gevent-synced queue with items from a client."""
        self.messages.put(message)


