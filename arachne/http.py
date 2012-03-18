#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Http support for spider activity."""

import requests
from arachne.conf import merge
from urllib import urlencode
from urlparse import urljoin
import ujson as json

json_types = (
    'application/json',
    'application/javascript',
    'text/javascript',
    'text/json',
)

def _url(*a, **kw):
    """Return a url for a requests.get call."""
    if 'params' in kw:
        return '%s?%s' % (a[0], urlencode(kw['params']))
    return a[0]

class Getter(object):
    """A simple getter that uses the basic 'get' but stores default base
    url, params, and headers."""
    def __init__(self, base_url, params={}, headers={}):
        self.base_url = base_url
        self.default_params = params.copy()
        self.default_headers = headers.copy()

    def get(self, url, *a, **kw):
        url = join(self.base_url, url)
        kw['params'] = merge(self.default_params, kw.get('params', {}))
        kw['headers'] = merge(self.default_headers, kw.get('headers', {}))
        return get(url, *a, **kw)

def join(*parts):
    return '/'.join([p.strip('/') for p in parts])

def get(*a, **kw):
    is_json = kw.pop('json', False)
    response = requests.get(*a, **kw)
    if response.headers['content-type'] in json_types or is_json:
        response.json = json.loads(response.content)
    return response

get.__doc__ = requests.get.__doc__

