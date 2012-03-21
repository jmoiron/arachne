#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Http support for spider activity."""

import requests
import ujson as json

import umemcache
from functools import wraps
from urllib import urlencode
from urlparse import urljoin
from arachne.conf import merge, settings, merge

# OAuth v1.0a support from requests-oauth
from oauth_hook import OAuthHook

json_types = (
    'application/json',
    'application/json;charset=UTF-8', # linkedin
    'application/javascript',
    'text/javascript',
    'text/json',
)

class HttpError(Exception):
    def __init__(self, response):
        self.message = "%d encountered getting \"%s\"" % (response.status_code, response.url)
        self.response = response
        super(HttpError, self).__init__(self.message)

def _url(*a, **kw):
    """Return a url for a requests.get call."""
    if 'params' in kw:
        return '%s?%s' % (a[0], urlencode(kw['params']))
    return a[0]

def oauth_client(token, secret, consumer_key, consumer_secret, header_auth=False):
    """An OAuth client that can issue get requests."""
    hook = OAuthHook(token, secret, consumer_key, consumer_secret, header_auth)
    client = requests.session(hooks={'pre_request': hook})
    client.get = wrapget(client.get)
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
    def __init__(self, base_url, params={}, headers={}, ignore_errors=False):
        self.base_url = base_url
        self.default_params = params.copy()
        self.default_headers = headers.copy()
        self.ignore_errors = ignore_errors

    def get(self, url, *a, **kw):
        url = join(self.base_url, url)
        kw['params'] = merge(self.default_params, kw.get('params', {}))
        kw['headers'] = merge(self.default_headers, kw.get('headers', {}))
        kw['ignore_errors'] = self.ignore_errors
        return get(url, *a, **kw)

def join(*parts):
    parts = filter(None, parts)
    url = '/'.join([p.strip('/') for p in parts])
    if parts[-1][-1] == '/':
        url = url + '/'
    return url

def wrapget(func):
    """Wrap requests' `get` function with utility, convenience, book-keeping."""
    @wraps(func)
    def wrapped(*a, **kw):
        """This adds a few things to get.  First, it can raise exceptions on
        errored status codes in the 400's and 500's, which can clean up a lot
        of plugin code that would otherwise have to check for that.  It also
        auto-loads json content and puts it on response.json."""
        ignore_errors = kw.pop('ignore_errors', True)
        is_json = kw.pop('json', False)
        response = func(*a, **kw)
        if response.headers['content-type'] in json_types or \
           response.headers['content-type'].startswith('application/json') or is_json:
            response.json = json.loads(response.content)
        # if an error occured and we waned to raise an exception, do it;  we
        # can still take the response off of this error
        if response.status_code > 400 and not ignore_errors:
            raise HttpError(response)
        return response
    return wrapped

get = wrapget(requests.get)

