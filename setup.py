#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Setup script for arachne."""

from setuptools import setup, find_packages
import sys, os

from arachne import VERSION
version = '.'.join(map(str, VERSION))

# some trove classifiers:

# License :: OSI Approved :: MIT License
# Intended Audience :: Developers
# Operating System :: POSIX

setup(
    name='arachne',
    version=version,
    description="scalable web spider",
    long_description=open('README.rst').read(),
    # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha'
    ],
    keywords='spider gevent requests rabbitmq',
    author='Jason Moiron',
    author_email='jmoiron@jmoiron.net',

    url='http://github.com/jmoiron/arachne',
    license='MIT',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    test_suite="tests",
    install_requires=[
        "umysql",
        "umemcache",
        "pycassa",
        "requests",
        "requests-oauth",
        "ujson",
        "gevent",
        "kombu",
        "humanize",
        "flask",
    ],
    entry_points="""
    # -*- Entry points: -*-
    """,
)
