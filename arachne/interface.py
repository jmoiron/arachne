#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A gevent/wsgi/flask re-implementation of the interface server."""

import sys
from gevent.wsgi import WSGIServer
from flask import Flask, request, jsonify, abort
from arachne import plugin
from arachne.utils import argspec
from arachne.conf import settings, merge
import traceback

class Config(object):
    DEBUG = True
app = Flask(__name__)
app.config.from_object(Config())

@app.errorhandler(404)
def not_found(error):
    response = jsonify({'ok': False, 'error': error.message})
    response.status_code = 404
    return response

@app.route('/')
def index():
    return jsonify(**{"ok": True})

@app.route('/info/')
def info():
    return jsonify(**{"ok": True})

@app.route('/plugins/')
def plugins():
    return jsonify(**{'plugins': plugin.registry.keys(), 'count': len(plugin.registry)})

@app.route('/<name>/')
def plugin_info(name):
    if name in plugin.registry:
        plug = plugin.registry[name]
        methods = dict([(plugname,
            {'path': '/%s/%s/' % (name, plugname),
             'spec': argspec(method)}) for plugname,method in plug.methods.items()])
        return jsonify(**dict(name=name, methods=methods))
    abort(404)

# FIXME: in the future, it should be possible to get info from HTTP
# on each plugin function with GET, and we should send our requests
# as POST.
@app.route('/<name>/<function>/', methods=['GET', 'POST'])
def plugin_function(name, function):
    if name not in plugin.registry:
        abort(404)
    plug = plugin.registry[name]
    if function not in plug.methods:
        abort(404)
    method = plug.methods[function]
    if request.method == 'POST':
        response = jsonify(ok=False, error="POST not yet supported.")
        response.status_code = 500
        return response
    else:
        content = settings.server.run_method(method, **clean(request.args))
        if isinstance(content, (dict, list)):
            return jsonify(**content)
        return content, 500

def serve(port=5000):
    server = WSGIServer(('', port), app)
    server.serve_forever()

def clean(args):
    """Returns singular values for multidict keys if the length is one."""
    return dict([(k,v[0]) if len(v) == 1 else (k,v) for k,v in args.iteritems()])

if __name__ == "__main__":
    try: serve()
    except KeyboardInterrupt: pass
