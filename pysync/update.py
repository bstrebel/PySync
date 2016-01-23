#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, logging, json
from pyutils import LogAdapter, get_logger, strflocal

from abc import ABCMeta, abstractmethod, abstractproperty

class ThisFromThat(object):

    __metaclass__ = ABCMeta

    def __init__(self, engine, other, package):
        self._engine = engine
        self._other = other
        self._update = None
        self._adapter = LogAdapter(engine._logger, {'package': package})

    @property
    def logger(self):
        return self._adapter

    @property
    def class_name(self):
        return self._engine.class_name

    @property
    def options(self):
        return self._engine.options

    def update(self, other, that=None, this=None):

        self._update = True if this is None else False

        if self._update:

            # assert: refernce == child of Sync class
            self._other = other
            that = self._other.get()
            this = self._engine.get()
            # TODO: check return, raise exception (?)
            title = this.title if isinstance(this.title, unicode) else this.title.decode('utf-8')
            self.logger.info(u'%s: Updating [%s] from %s' % (self.class_name, title, other.class_name))

        # TODO: check todo, raise exception (?)
        return that, this
