#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, logging, json
from pyutils import LogAdapter, get_logger, strflocal

from abc import ABCMeta, abstractmethod, abstractproperty

class Sync(object):

    __metaclass__ = ABCMeta

    def __init__(self, options, logger=None, package='sync'):

        if logger is None:
            self._logger = get_logger('sync', logging.DEBUG)
        else:
            self._logger = logger

        self._adapter = LogAdapter(self._logger, {'package': package})

        self._options = options
        self._key = None
        self._items = {}

    @property
    def logger(self): return self._adapter

    @property
    def options(self): return self._options

    @property
    def items(self): return self._items

    def _add_item(self, id, tm, key):

            self._items[id] = {}
            self._items[id]['time'] = tm

            if isinstance(key, str):
                self._items[id]['key'] = key.decode('utf-8')
            else:
                self._items[id]['key'] = key

            self.logger.debug('%s %s %s %s' % (self.class_name, id, strflocal(tm), self._items[id]['key']))

    def get_item(self, key=None):
        if key is None:
            key = self._key
        return self._items.get(key)

    def __delitem__(self, key):
        del self._items[key]

    def __getitem__(self, key):
        self._key = key
        return self._items.get(key)

    def __iter__(self):
        for self._key in self._items:
            #yield self._items[self._key]
            yield self._key

    def find_key(self, key):
        for id in self._items:
            if self._items[id]['key'] == key:
                return id
        return None

    def dump_item(self, key=None):
        if key is None: key = self._key
        return json.dumps(self._items[key], ensure_ascii=False, encoding='utf-8')

    @property
    def key(self): return self._key

    def end_session(self):
        return None

    @abstractmethod
    def sync_map(self, what, compare):
        return None

    @abstractmethod
    def create(self, that):
        return None, None

    @abstractmethod
    def update(self, this, that):
        return None

    @abstractmethod
    def get(self):
        return None

    @abstractmethod
    def delete(self):
        self.logger.info('%s: Delete %s' % (self.class_name, self.dump_item()))
        del self._items[self.key]
