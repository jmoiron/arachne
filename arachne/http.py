#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Http support for spider activity."""

import requests
import ujson as json
from time import time, mktime
from contextlib import contextmanager
from datetime import datetime
from dateutil.parser import parse as dateparse

from functools import wraps
from urllib import urlencode
from urlparse import urljoin
from hashlib import md5

from arachne import memcached
from arachne.conf import merge, settings, require
from arachne.utils import encode, decode

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

class CacheHit(Exception):
    pass

# -- utils --

def requests_url(*a, **kw):
    """Return a url for a requests.get call."""
    if 'params' in kw:
        return '%s?%s' % (a[0], urlencode(kw['params']))
    return a[0]

def join(*parts):
    """A version of urljoin which works on more than one argument."""
    parts = filter(None, parts)
    url = '/'.join([p.strip('/') for p in parts])
    if parts[-1][-1] == '/':
        url = url + '/'
    return url

# -- Oauth --

def oauth_client(token, secret, consumer_key, consumer_secret, header_auth=False):
    """An OAuth client that can issue get requests."""
    hook = OAuthHook(token, secret, consumer_key, consumer_secret, header_auth)
    client = requests.session(hooks={'pre_request': hook})
    client.get = wrapget(client.get)
    return client

# -- HTTP Get wrappers --

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
    url, params, and headers.  Very similar to request's sessions."""
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

def wrapget(func):
    """Wrap requests' `get` function with utility, convenience, book-keeping."""
    # wrap with cache manager
    func = cache_manager(func)

    @wraps(func)
    def wrapped(*a, **kw):
        """This adds a few things to get.  First, it can raise exceptions on
        errored status codes in the 400's and 500's, which can clean up a lot
        of plugin code that would otherwise have to check for that.  It also
        auto-loads json content and puts it on response.json."""
        ignore_errors = kw.pop('ignore_errors', True)
        is_json = kw.pop('json', False)

        response = func(*a, **kw)
        # parse json
        if response.headers['content-type'] in json_types or \
           response.headers['content-type'].startswith('application/json') or is_json:
            response.json = json.loads(response.content)
        # if an error occured and we waned to raise an exception, do it;  we
        # can still take the response off of this error
        if response.status_code > 400 and not ignore_errors:
            raise HttpError(response)

        return response
    return wrapped

# -- Header/Cache management --

def cache_manager(func):
    """Another decorator for requests.get which manages the header cache."""
    @wraps(func)
    def wrapper(*a, **kw):
        url = requests_url(*a, **kw)
        ch = header_cache.get(url)
        if "expires" in ch and ch["expires"] > utcnow():
            raise CacheHit("Expires in the future.")

        kw.setdefault("headers", {}).update(ch)

        response = func(*a, **kw)

        if response.status_code == 304:
            raise CacheHit("304 status code.")

        # set cache control headers if available
        ch = cache_headers(response.headers)
        if ch:
            header_cache.set(url, cache_headers(response.headers))
        return response
    return wrapper

def utcnow():
    """Return a timestamp for the present UTC time."""
    return mktime(datetime.utcnow().timetuple())

def to_timestamp(text):
    """Return a unix timestamp for some text."""
    return mktime(dateparse(text).timetuple())

def cache_headers(headers):
    """Given headers as a dictionary from a requests response object, return
    the cache control headers to pass into the next request.  It's these
    headers that are eventually saved to memcached and used on future requests
    to the same URL."""
    now = utcnow()
    header = {}
    if "expires" in headers:
        expires = to_timestamp(headers["expires"])
        if expires > now:
            header["expires"] = expires
    if "last-modified" in headers:
        header["if-modified-since"] = headers["last-modified"]
    if "etag" in headers:
        header["if-none-match"] = headers["etag"]

    # ignore "expires" if last-modified or etags are present
    if "expires" in header and len(header) > 1:
        header.pop("expires")

    return header

def disable_header_cache():
    """Utility function to disable the header cache."""
    global header_cache
    header_cache = DummyHeaderCache()

def enable_header_cache(**kw):
    """Utility function to enable the header cache with arguments."""
    global header_cache
    header_cache = HeaderCache(**kw)

class HeaderCache(object):
    """Keeps a cache of url headers."""
    def __init__(self, **kw):
        # use specialized cache if available, else default cache location
        self.config = merge(settings.like("header_cache"), kw)
        self.config = merge(settings.like("memcached"), self.config)
        self.client = memcached.Memcached(**self.config)

    def get(self, url):
        result = self.client.get('hc-%s' % md5(url).hexdigest())
        return decode(result) if result else {}

    def set(self, url, header):
        key = 'hc-%s' % md5(url).hexdigest()
        if "expires" in header:
            self.client.set(key, encode(header), header["expires"] - utcnow())
        self.client.set(key, encode(header))

class DummyHeaderCache(HeaderCache):
    def __init__(self, **kw): pass
    def get(self, url): return {}
    def set(self, url, header): return


# -- static modifications --

header_cache = HeaderCache() if settings.enable_header_cache else DummyHeaderCache()
get = wrapget(requests.get)

