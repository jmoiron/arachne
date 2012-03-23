#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Rate limiting functionality using memcached counters and the algorithm
roughly described by Simon Willison here:

    http://simonwillison.net/2009/jan/7/ratelimitcache/

Essentially, rate limits are configured around the application.  When a
resource is about to be requested, a check is made that using that resource
will obey established limits.  If the token returned is True, then the
process can proceed.
"""

from hashlib import md5
from time import strftime, gmtime, time
import math
import logging

from arachne.conf import settings
from arachne.memcached import Memcached

logger = logging.getLogger(__name__)

limits = {}

def get_token(self, resource):
    """Returns True if the resource in question has been used under the rate
    limit or False if it has not been."""
    if resource not in limits:
        return True
    return limits[resource].token()

def window(interval, count=4):
    """Return the previous count timestamps for the interval, which is
    in minutes.  So if the interval is 1 minute and the count is 3,
    return now, 20 seconds ago, and 40 seconds ago, floored to the same
    20 second intervals no matter what the current time is."""
    seconds = (interval * 60)/count
    now = math.floor(time()/seconds)*seconds
    return [str(int(now-x)) for x in range(0, interval*60, seconds)]

class RateLimit(object):
    """Rate limiter which uses sub-sequences of 4 keys for two levels of rate
    limiting granularity:  every 10 seconds for a sliding window of one minute
    and every 10 minutes for a sliding window of one hour."""
    def __init__(self, resource, per_minute=0, per_5_minutes=0, per_hour=0):
        self.resource = resource
        self.limits = {}
        if per_minute:
            self.limits["per_minute"] = (per_minute, 60)
        if per_5_minutes:
            self.limits["per_5_minutes"] = (per_5_minutes, 300)
        if per_hour:
            self.limits["per_hour"] = (per_hour, 3600)
        if not self.limits:
            return
        self.key = md5(resource).hexdigest()
        limits[resource] = self

    def token(self):
        for limit, (rate, interval) in self.limits.iteritems():
            timestamps = window(interval)
            keys = [self.key+timestamp for timestamp in timestamps]
            results = ratelimit_cache.get_multi(*keys)
            gets = sum(map(int, results.values()))
            if gets >= rate:
                logger.error("RateLimit %s exceeded for %s" % (limit, self.resource))
                return False
            if self.key+timestamps[0] not in results:
                ratelimit_cache.add(self.key+timestamps[0], '0')
            ratelimit_cache.incr(self.key+timestamps[0], 1)
        return True

if not settings.get("disable_ratelimit", False):
    ratelimit_cache = Memcached(**settings.like("ratelimit_cache"))
else:
    ratelimit_cache = None

def enable():
    global ratelimit_cache
    ratelimit_cache = Memcached(**settings.like("ratelimit_cache"))

def disable():
    global ratelimit_cache
    ratelimit_cache = None

