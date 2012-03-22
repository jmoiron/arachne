#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A gevent/wsgi/flask re-implementation of the interface server."""

import sys
import ujson as json
from humanize.time import naturaldelta
from flask import Flask, Response, request, abort
from arachne import plugin, http
from arachne.utils import argspec
from arachne.conf import settings
import traceback

class Config(object):
    DEBUG = True
app = Flask(__name__)
app.config.from_object(Config())

def jsonify(*a, **kw):
    resp = json.dumps(kw) if kw and not a else json.dumps(a[0])
    return Response(resp, 200, headers={'content-type': 'application/json'})

@app.errorhandler(404)
def not_found(error):
    response = jsonify({'ok': False, 'error': str(error)})
    response.status_code = 404
    return response

@app.route('/')
def index():
    return jsonify(ok=True)

@app.route('/info/')
def info():
    return jsonify(ok=True)

@app.route('/plugins/')
def plugins():
    return jsonify(plugins=plugin.registry.keys(), count=len(plugin.registry))

def naturalinterval(secs):
    string = naturaldelta(secs)
    string = string.replace('a ', '').replace("an ", "")
    return "every %s" % string

def methods_for(plugin):
    return dict([(name, {
        "path": "/%s/%s/" % (plugin.plugin_name, name),
        "spec": argspec(method),
        "interval": method.interval,
        "human-interval": naturalinterval(method.interval),
    }) for name,method in plugin.methods.iteritems()])

@app.route("/methods/")
def methods():
    ret = {}
    for name,plug in plugin.registry.items():
        ret[name] = methods_for(plug)
    return jsonify(ret)

@app.route('/<name>/')
def plugin_info(name):
    if name in plugin.registry:
        return jsonify(name=name, methods=methods_for(plugin.registry[name]))
    abort(404)

# FIXME: in the future, it should be possible to get info from HTTP
# on each plugin function with GET, and we should send our requests
# as POST.

@app.route('/<name>/<function>', methods=['GET', 'POST'])
def plugin_function_noslash(name, function):
    return plugin_function(name, function)

def proxy(request):
    params = dict(request.args.items())
    url = http.join(settings.server.proxy, request.path)
    try:
        result = http.get(url, params=params, json=True)
        return jsonify(result.json)
    except:
        return traceback.format_exc(), 500

@app.route('/<name>/<function>/',methods=['GET', 'POST'])
def plugin_function(name, function):
    method = plugin.registry.by_path("%s/%s" % (name, function))
    if not method:
        if settings.server.proxy:
            return proxy(request)
        abort(404)
    if request.method == 'POST':
        response = jsonify(ok=False, error="POST not yet supported.")
        response.status_code = 500
        return response
    else:
        content = settings.server.run_method(method, **clean(request.args))
        if isinstance(content, (dict, list)):
            return jsonify(content)
        elif isinstance(content, basestring):
            if "Traceback" in content:
                return content, 500
            return content, 200

def clean(args):
    """Returns singular values for multidict keys if the length is one."""
    return dict([(k,v[0]) if len(v) == 1 else (k,v) for k,v in args.iteritems()])

if __name__ == "__main__":
    try: serve()
    except KeyboardInterrupt: pass
