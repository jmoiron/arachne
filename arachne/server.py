#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""servers."""

from uuid import uuid4
from time import time, mktime
import gevent
from gevent.wsgi import WSGIServer
from arachne.conf import settings
from arachne.utils import argspec, Heap

import traceback

class Server(object):
    def __init__(self, *a, **kw):
        settings.server = self
        self.greenlets = []

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

    def serve(self, port, app, block=False):
        from gevent.wsgi import WSGIServer
        server = WSGIServer(('', port), app)
        if not block:
            self.greenlets.append(gevent.spawn(server.serve_forever))
        else:
            server.serve_forever()

class SchedulerServer(Server):
    def __init__(self, port=settings.port, plugins=[], debug=False, app=None):
        super(SchedulerServer, self).__init__()
        self.port = settings.like("scheduler_server").get("port", 8070)
        self.state = "stopped"
        self.greenlets = []
        self.port = port
        self.plugins = [p() for p in plugins]
        self.jobheap = Heap()
        self.app = app

    def start(self):
        from arachne import amqp
        if not self.app:
            from arachne.web import scheduler
            self.app = scheduler.app
        self.queue = amqp.Amqp()
        self.state = "initializing"
        self.serve(self.port, self.app)
        self.update_queue_status(self.queue)
        self.run()

    def update_queue_status(self, queue):
        def updater():
            while 1:
                self.queue_status = queue.status()
                gevent.sleep(10)
        self.greenlets.append(gevent.spawn(updater))


    def run(self):
        """Subclass and implement a scheduler that puts jobs on self.queue."""
        self.state = "running"
        while 1:
            gevent.sleep(1)

    def shutdown(self):
        pass


class WorkerServer(Server):
    def __init__(self, port=settings.port, plugins=[], debug=False):
        super(InterfaceServer, self).__init__()
        self.plugins = [p() for p in plugins]
        self.port = port

    def start(self):
        pass

class InterfaceServer(Server):
    def __init__(self, port=settings.port, plugins=[], debug=False):
        super(InterfaceServer, self).__init__()
        self.plugins = [p() for p in plugins]
        self.port = port

    def start(self):
        from arachne.web import interface
        from arachne.cassandra import Cassandra
        self.datastore = Cassandra()
        self.serve(self.port, interface.app, True)

    def run_method(self, method, **args):
        """Run a method and save its results to the datastore.  Returns either
        a string (on failures) or a dict to be sent to the client."""
        user_id = args.get('site_user_id', args.get('user_id', None))
        result = super(InterfaceServer, self).run_method(method, **args)
        # XXX: is this really enough of a "success" condition?
        if user_id and isinstance(result, (dict, list)):
            uuid = uuid4().hex
            self.datastore.set(user_id, result, uuid)
            return {uuid: result}
        return result



