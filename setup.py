#!/usr/bin/env python
# vi:si:et:sw=4:sts=4:ts=4
# encoding: utf-8
try:
    from setuptools import setup
except:
    from distutils.core import setup

def get_bzr_version():
    import os
    import re
    info = os.path.join(os.path.dirname(__file__), '.bzr/branch/last-revision')
    changelog = os.path.join(os.path.dirname(__file__), 'debian/changelog')
    if os.path.exists(info):
        f = open(info)
        rev = int(f.read().split()[0])
        f.close()
        if rev:
            return u'%s' % rev
    elif os.path.exists(changelog):
        f = open(changelog)
        head = f.read().strip().split('\n')[0]
        f.close()
        rev = re.compile('\d+\.\d+\.(\d+)').findall(head)
        if rev:
            return u"%s" % rev[0]
    return u'unknown'

setup(
    name="pandora_client",
    version="0.2.%s" % get_bzr_version() ,
    description='''pandora_client is a commandline client for pan.do/ra.
You can use it to import videos into a pan.do/ra system.
It is currently known to work on Linux and Mac OS X.
''',
    author="j",
    author_email="j@mailb.org",
    url="http://wiki.0x2620.org/wiki/pandora_client",
    download_url="http://code.0x2620.org/pandora_client/download",
    license="GPLv3",
    scripts = [
        'bin/pandora_client',
    ],
    packages=[
        'pandora_client'
    ],
    install_requires=[
        'ox >= 2.1.541',
        'requests >= 1.1.0'
    ],
    keywords = [
],
    classifiers = [
      'Operating System :: OS Independent',
      'Programming Language :: Python',
      'License :: OSI Approved :: GNU General Public License (GPL)',
    ],
)
