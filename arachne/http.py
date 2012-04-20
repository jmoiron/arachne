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
from urllib import urlencode, quote
from urlparse import urljoin, parse_qs
from hashlib import md5

from arachne import memcached
from arachne.conf import merge, settings, require
from arachne.utils import encode, decode

# OAuth v1.0a support from requests-oauth
from oauth_hook import OAuthHook

import logging

logger = logging.getLogger(__name__)

json_types = (
    'application/json',
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

def mdict2sdict(mdict):
    """Turn a multidict into a singledict for single element lists in the dict."""
    return dict([(k, v[0] if isinstance(v, list) and len(v) == 1 else v) for k,v in mdict.iteritems()])

def requests_url(*a, **kw):
    """Return a url for a requests.get call."""
    if 'params' in kw:
        return '%s?%s' % (a[0], urlencode(kw['params']))
    return a[0]

def cgi_clean(result):
    return mdict2sdict(parse_qs(result))

def join(*parts):
    """A version of urljoin which works on more than one argument."""
    parts = filter(None, parts)
    url = '/'.join([p.strip('/') for p in parts])
    if parts[-1][-1] == '/':
        url = url + '/'
    return url

# -- Oauth --

def oauth_client(token, secret, consumer_key, consumer_secret, header_auth=True):
    """An OAuth client that can issue get requests."""
    hook = OAuthHook(token, secret, consumer_key, consumer_secret, header_auth)
    client = requests.session(hooks={'pre_request': hook})
    client.get = wrapget(client.get)
    client.post = wrapget(client.post)
    return client

# -- HTTP Get wrappers --

class OAuthTokenGetter(object):
    """A getter for requesting tokens and authorizing those tokens."""
    def __init__(self, consumer_key, consumer_secret, **kw):
        self.client_params = {
            'consumer_key': consumer_key,
            'consumer_secret': consumer_secret,
            'header_auth': True}
        self.client_params.update(kw)
        self.key = consumer_key
        self.secret = consumer_secret

    def request_token(self, url, **kw):
        """Request an unauthorized token at the request token url.  kws passed
        to requests.get"""
        hook = OAuthHook(**self.client_params)
        client = requests.session(hooks={'pre_request': hook})
        response = client.get(url, **kw)
        data = cgi_clean(response.text)
        return dict(secret=data["oauth_token_secret"], key=data["oauth_token"])

    def access_token(self, url, token_key, token_secret, **kw):
        """Authorize the unauthorized token using the verifier."""
        header_auth = kw.pop('header_auth', True)
        if "verifier" in kw:
            kw['oauth_verifier'] = kw.pop("verifier")
        client = oauth_client(token_key, token_secret, self.key, self.secret, header_auth=header_auth)
        response = client.get(url, params=kw, cache=False).text
        data = cgi_clean(response)
        # XXX: Compatability with old oauth library only, should eventually migrate off
        if "oauth_token_secret" not in data:
            logger.error("OAuth access token error: %s (%s)" % (data, response))
        data["secret"] = data["oauth_token_secret"]
        data["key"] = data["oauth_token"]
        return data


class OAuthGetter(object):
    """A getter that will sign requests with OAuth v1.0a headers/url params."""
    def __init__(self, base_url, token, secret, key, key_secret,
            header_auth=True, params={}, headers={}):
        self.client = oauth_client(token, secret, key, key_secret, header_auth)
        self.base_url = base_url
        self.default_params = params.copy()
        self.default_headers = headers.copy()

    def get(self, url, *a, **kw):
        url = join(self.base_url, url)
        kw['params'] = merge(self.default_params, kw.get('params', {}))
        kw['headers'] = merge(self.default_headers, kw.get('headers', {}))
        return self.client.get(url, *a, **kw)

    def post(self, url, *a, **kw):
        url = join(self.base_url, url)
        kw['params'] = merge(self.default_params, kw.get('params', {}))
        kw['headers'] = merge(self.default_headers, kw.get('headers', {}))
        return self.client.post(url, *a, **kw)

    @classmethod
    def partial(cls, url, key, key_secret, header_auth=True, params={}, headers={}):
        """Returns a method that will build an OAuthGetter based on the parameters."""
        def closure(token, secret):
            return OAuthGetter(url, token, secret, key, key_secret,
                header_auth=header_auth, params=params, headers=headers)
        return closure

class Getter(object):
    """A simple getter that uses the basic 'get' but stores default base
    url, params, and headers.  Very similar to request's sessions."""
    def __init__(self, base_url, params={}, headers={}, data={}, ignore_errors=False):
        self.base_url = base_url
        self.default_params = params.copy()
        self.default_headers = headers.copy()
        self.default_data = data.copy()
        self.ignore_errors = ignore_errors

    def get(self, url, *a, **kw):
        url = join(self.base_url, url)
        kw['params'] = merge(self.default_params, kw.get('params', {}))
        kw['headers'] = merge(self.default_headers, kw.get('headers', {}))
        kw['ignore_errors'] = self.ignore_errors
        return get(url, *a, **kw)

    def post(self, url, *a, **kw):
        url = join(self.base_url, url)
        kw['params'] = merge(self.default_params, kw.get('params', {}))
        kw['headers'] = merge(self.default_headers, kw.get('headers', {}))
        kw['data'] = merge(self.default_data, kw.get('data', {}))
        kw['ignore_errors'] = self.ignore_errors
        return post(url, *a, **kw)


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
        if response.headers['content-type'].split(';')[0] in json_types or is_json:
            response.json = json.loads(response.content) if response.content else {}
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
        # allow the caller to set nocache
        if not kw.pop('cache', True):
            return func(*a, **kw)

        url = requests_url(*a, **kw)
        if settings.enable_header_cache:
            ch = header_cache.get(url)
            if ch:
                if "expires" in ch and ch["expires"] > utcnow():
                    raise CacheHit("Expires in the future.")
                kw.setdefault("headers", {}).update(ch)

        response = func(*a, **kw)

        if response.status_code == 304:
            raise CacheHit("304 status code.")
        # set cache control headers if available
        if settings.enable_header_cache:
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
    settings.enable_header_cache = False
    header_cache = DummyHeaderCache()

def enable_header_cache(**kw):
    """Utility function to enable the header cache with arguments."""
    global header_cache
    settings.enable_header_cache = True
    header_cache = HeaderCache(**kw)

class HeaderCache(object):
    """Keeps a cache of url headers."""
    def __init__(self, **kw):
        # use specialized cache if available, else default cache location
        self.config = merge(settings.like("memcached"), settings.like("header_cache"), kw)
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
post = wrapget(requests.post)
head = wrapget(requests.head)

