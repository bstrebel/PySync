#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, logging, json
from pyutils import LogAdapter, get_logger, strflocal, utf8

from abc import ABCMeta, abstractmethod, abstractproperty

class SyncError(Exception):
    pass

class SyncSessionError(SyncError):
    pass

class SyncInitError(SyncError):
    pass

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

        self._filter_expr = options.get('filter_expr')
        self._filter_module = options.get('filter_module')

        self._deleted = {}
        self._modified = {}
        self._created = {}

    def __repr__(self): return self.label

    def __str__(self): return self.label

    @property
    def class_name(self): return self.label

    @property
    def logger(self): return self._adapter

    @property
    def options(self): return self._options

    @property
    def label(self): return self._options.get('label')

    @property
    def signature(self): return self._options.get('signature')

    @property
    def items(self): return self._items

    @property
    def key(self): return self._key

    @property
    def title(self):
        if self._items.get(self._key) and self._items[self._key].get('key'):
            return utf8(self._items[self._key]['key'])
        return None

    def _add_item(self, id, item):
            self._items[id] = item
            self.logger.debug(u'%s %s %s' % (self.class_name, id, item))

    @abstractmethod
    def map_item(self, key=None):
        if key is None: key = self._key
        item = self._items.get(key)
        if item:
            return {'id': item['id'], 'key': item['key'], 'time': item['time']}
            #return {'id': item._id, 'key': item._key, 'time': item._time}
        else:
            return None

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


    @classmethod
    def end_session(cls, logger, **kwargs):
        if logger:
            logger.debug(u'End session called for [%s]' % (cls))

    def commit_sync(self, lr, opts, logger):
        return opts

    def _check_filter(self, item):
        ok = False
        if self._filter_expr is not None:
            ok = eval(self._filter_expr)
        elif self._filter_module is not None:
            ok = self._filter_module.check_filter(item)
        else:
            ok = True
        return ok

    @abstractproperty
    def need_last_map(self):
        return False

    @abstractmethod
    def sync_map(self, last=None):
        return None

    @abstractmethod
    def create(self, that, sid=None):
        return None, None

    def update(self, other, that=None, this=None, sid=None):

        from pysync import OxTaskSync, EnClientSync, ToodledoSync
        from oxsync import OxTaskFromEvernote, OxTaskFromToodldo
        from tdsync import ToodledoFromOxTask, ToodledoFromEvernote
        from ensync import EvernoteFromOxTask, EvernoteFromToodledo

        try:
            if isinstance(self, ToodledoSync):
                if isinstance(other, OxTaskSync):
                    return self.map_item(ToodledoFromOxTask(self, other).update(other, that=that, this=this, sid=sid))
                if isinstance(other, EnClientSync):
                    return self.map_item(ToodledoFromEvernote(self, other).update(other, that=that, this=this, sid=sid))

            if isinstance(self, EnClientSync):
                if isinstance(other, OxTaskSync):
                    return self.map_item(EvernoteFromOxTask(self, other).update(other, that=that, this=this, sid=sid))
                if isinstance(other, ToodledoSync):
                    return self.map_item(EvernoteFromToodledo(self, other).update(other, that=that, this=this, sid=sid))

            if isinstance(self, OxTaskSync):
                if isinstance(other, EnClientSync):
                    return self.map_item(OxTaskFromEvernote(self, other).update(other, that=that, this=this, sid=sid))
                if isinstance(other, ToodledoSync):
                    return self.map_item(OxTaskFromToodldo(self, other).update(other, that=that, this=this, sid=sid))
        except Exception as e:
            self.logger.exception('Update failed. Check stack trace for details!')
            return None

        else:
            error = u'%s: Updating from [%s] not supported' % (self.class_name, other.class_name)
            self.logger.error(error)

    @abstractmethod
    def get(self):
        return None

    @abstractmethod
    def delete(self, sid=None):
        self.logger.debug(u'%s: Delete %s' % (self.class_name, self.dump_item()))
        if sid is not None:
            del self._items[self.key]

    @abstractmethod
    def changed(self, sync):
        item = self._items.get(self._key)
        if sync['time'] < item['time']:
            return True
        else:
            return False
