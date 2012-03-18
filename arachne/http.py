#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Http support for spider activity."""

import requests
from urllib import urlencode
from urlparse import urljoin
import ujson as json

json_types = (
    'application/json',
    'application/javascript',
    'text/javascript',
    'text/json',
)

class Getter(object):
    """A simple getter that uses the basic 'get' but stores default base
    urls and params."""
    def __init__(self, base_url, default_params={}):
        self.base_url = base_url
        self.default_params = default_params.copy()

    def get(self, url, *a, **kw):
        url = urljoin(self.base_url, url)
        kw['params'] = merge(kw.get('params', {}), self.default_params)
        return get(url, *a, **kw)


def join(*parts):
    return '/'.join([p.strip('/') for p in parts])

def get(*a, **kw):
    isjson = kw.pop('json', False)
    response = requests.get(*a, **kw)
    if response.headers['content-type'] in json_types or isjson:
        response.json = json.loads(response.content)
    return response
get.__doc__ = requests.get.__doc__

