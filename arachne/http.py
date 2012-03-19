#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Http support for spider activity."""

import requests
from functools import wraps
from arachne.conf import merge
from urllib import urlencode
from urlparse import urljoin
import ujson as json

# OAuth v1.0a support from requests-oauth
from oauth_hook import OAuthHook

json_types = (
    'application/json',
    'application/json;charset=UTF-8', # linkedin
    'application/javascript',
    'text/javascript',
    'text/json',
)

def _url(*a, **kw):
    """Return a url for a requests.get call."""
    if 'params' in kw:
        return '%s?%s' % (a[0], urlencode(kw['params']))
    return a[0]

def oauth_client(token, secret, consumer_key, consumer_secret, header_auth=False):
    """An OAuth client that can issue get requests."""
    hook = OAuthHook(token, secret, consumer_key, consumer_secret, header_auth)
    client = requests.session(hooks={'pre_request': hook})
    client.get = _get_wrapper(client.get)
    return client

class OAuthGetter(object):
    """A getter that will sign requests with OAuth v1.0a headers/url params."""
    def __init__(self, base_url, token, secret, key, key_secret,
            header_auth=False, params={}, headers={}):
        self.client = oauth_client(token, secret, key, key_secret, header_auth)
        self.base_url = base_url
        self.default_params = params.copy()
        self.default_headers = headers.copy()

    def get(self, url, *a, **kw):
        url = join(self.base_url, url)
        kw['params'] = merge(self.default_params, kw.get('params', {}))
        kw['headers'] = merge(self.default_headers, kw.get('headers', {}))
        return self.client.get(url, *a, **kw)

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

def _get_wrapper(func):
    """Wrap requests' `get` function with utility, convenience, book-keeping."""
    @wraps(func)
    def wrapped(*a, **kw):
        is_json = kw.pop('json', False)
        response = func(*a, **kw)
        if response.headers['content-type'] in json_types or is_json:
            response.json = json.loads(response.content)
        return response
    return wrapped

get = _get_wrapper(requests.get)

