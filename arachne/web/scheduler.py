#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Scheduler HTTP interface."""

import time
from arachne.conf import settings
from .interface import *

@app.route("/timing/")
def timing():
    return jsonify({"ok": True})

@app.route("/info/")
def info():
    server = settings.server
    return jsonify({
        "time": time.time(),
        "plugins": [p.plugin_name for p in server.plugins],
        "port": server.port,
        "state": server.state,
        "heap": {
            "length": len(server.jobheap.items),
            "next": server.jobheap[0],
        }
    })


