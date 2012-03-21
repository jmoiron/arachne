arachne
-------

Arachne is meant to be a next generation version of `hiispider`_, a flexible
web spider written at `hiidef`_ for `flavors.me`_.  It features a very similar
high level architecture, but implements them differently to achieve a few
important objectives:

 * HTTP interfaces should be rich and easily extendable
 * Plugins should be easy to run synchronously
 * DRY-ness in the resultant plugin code
 * Should not depend on undocumented architectural decisions

Asynchronicity is achieved with `gevent`_, which should be patched by users of
arachne.  Without patching, arachne behaves synchronously and nearly all of its
clients and libraries are usable from the python shell.

.. _hiidef: http://hiidef.com
.. _flavors.me: http://flavors.me
.. _hiispider: http://github.com/hiidef/hiispider
.. _gevent: http://www.gevent.org/

architectural overview
----------------------

Arachne is split up into 3 major pieces:

* A ``scheduler`` which puts jobs on a queue
* A ``worker`` which executes scheduled jobs
* An ``interface`` which runs jobs on demand via HTTP

Jobs are all tied to methods implemented in plugins.  Arachne makes certain
basic assumptions and decisions, and will take care of these problems:

* Mapping URLs to plugin methods
* Basic plugin execution and result storage
* Registration and lookup for available plugins
* Associating a run-interval (every n seconds) with each plugin method
* Daemonization, start/stop/restart & pidfiles

You will have to decide:

* What a "job" looks like coming on and off the queue
* Where and how to store plugin results
* How to schedule those jobs
* How to store data necessary to run the jobs

batteries
---------

Arachne comes with a number of batteries included:

* a simple no-magic configuration management system
* a rich http library, based on `requests`_ with:
   * header caching on a pluggable backend (eg. memcached)
   * header-based json/xml parsing with forced overrides
   * OAuth 1.0a helpers (via `requests-oauth`_)
   * alternate ``session`` style helpers w/ with base-url support
* a memcached wrapper based on `ultramemcache`_
* a mysql wrapper based on `ultramysql`_
* an AMQP client based on `kombu`_ and `amqplib`_
* a cassandra client based on `pycassa`_

All of these clients will attempt to auto-configure with arachne's configuration
management system.

.. _requests: http://python-requests.org
.. _requests-oauth: https://github.com/maraujop/requests-oauth
.. _ultramemcache: https://github.com/esnme/ultramemcache
.. _ultramysql: https://github.com/esnme/ultramysql
.. _amqplib: http://code.google.com/p/py-amqplib/
.. _kombu: http://packages.python.org/kombu/
.. _pycassa: https://github.com/pycassa/pycassa

