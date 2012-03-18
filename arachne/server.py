#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""servers."""

from uuid import uuid4
from gevent import spawn
from gevent.wsgi import WSGIServer
from arachne.conf import settings
from arachne.utils import argspec

import traceback

class Server(object):
    def run_method(self, method, **args):
        """Runs a method with some arguments, catching all manner of error
        conditions and logging them appropriately"""
        try:
            return method(**args)
        except TypeError, e:
            if "takes" in e.message and "arguments" in e.message:
                return "%s\nargspec: %s\n" % (traceback.format_exc(), argspec(method))
            return traceback.format_exc()
        except Exception, e:
            return traceback.format_exc()

class InterfaceServer(Server):
    def __init__(self, port=settings.port, plugins=[]):
        settings.server = self
        self.greenlets = []
        self.plugins = plugins
        self.port = port
        for plugin in plugins:
            plugin()

    def start(self):
        from arachne.cassandra import Cassandra
        self.datastore = Cassandra()
        self.serve()

    def run_method(self, method, **args):
        """Run a method and save its results to the datastore.  Returns either
        a string (on failures) or a dict to be sent to the client."""
        user_id = args.get('site_user_id', args.get('user_id', None))
        result = super(InterfaceServer, self).run_method(method, **args)
        if user_id and isinstance(result, dict):
            uuid = uuid4().hex
            self.datastore.set(user_id, result, uuid)
            return {uuid: result}
        return result

    def serve(self):
        """Serve the HTTP interface for the InterfaceServer.  Blocks the
        current greenlet, so spawn if you want it to happen in the background."""
        from arachne import interface
        interface.serve(self.port)


