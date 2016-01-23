#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, json, re, requests, logging
from pyutils import LogAdapter, strflocal, get_logger, utf8, string

from pysync import Sync
from tdapi import ToodledoAPI, ToodledoTask


class ToodledoSync(Sync):

    @staticmethod
    def compare_tags(sync, map):

        if sync is None: sync = []
        if map is None: map = []

        if len(sync) != len(map):
            return False

        l = len(sync)
        if l > 0:
            s = sorted(sync)
            m = sorted(map)
            for i in range(0,l-1):
                if s[i] != m[i]:
                    return False
                i += 1

        return True

    @staticmethod
    def extra(note):
        extra = None
        if note is not None:
                extra = {'tags': note.tags,
                         'reminderDoneTime': note.attributes.reminderDoneTime,
                         'reminderTime': note.attributes.reminderTime}
        return extra

    @staticmethod
    def session(options, _logger):
        if options:
            if options.get('session') is not None:
                if options.get('cache') is not None:
                    if options.get('tasks_cache') is not None:
                        if options.get('secrets'):
                            secrets = options['secrets']
                            if secrets.get('client_id'):
                                if secrets.get('client_secret'):
                                    return ToodledoAPI.get_session(session=options.get('session'),
                                                                   cache=options.get('cache'),
                                                                   tasks_cache=options.get('tasks_cache'),
                                                                   client_id=secrets['client_id'],
                                                                   client_secret=secrets['client_secret'],
                                                                   logger=_logger)
                        else:
                            msg = 'Missing secrets in Toodledo options'
                    else:
                        msg = 'Missing tasks cache file in Toodledo options'
                else:
                    msg = 'Missing cache file in Toodledo options'
            else:
                msg = 'Missing oauth2 session file in Toodledo options'
        else:
            msg = 'Missing Toodledo options'

        LogAdapter(_logger, {'package': 'tdsync'}).error(msg)
        return None

    def __init__(self, client, options, logger=None):

        self._key_attribute = options.get('key','title')
        # self._maxsize = None

        if isinstance(client, ToodledoAPI):
            self._client = client
        else:
            self._client = ToodledoAPI.get_session(**client)

        Sync.__init__(self, options, logger, 'tdsync')

        if options.get('signature') is None:
            signature = {'label': options.get('label')}
            self.options.update({'signature': signature})

    # @property
    # def maxsize(self): return self._maxsize
    #
    # @maxsize.setter
    # def maxsize(self, value): self._maxsize = value

    @property
    def client(self): return self._client

    @property
    def need_last_map(self): return True

    def _check_filter(self, item):
        return True

    def map_item(self, ref=None):
        if isinstance(ref, ToodledoTask):
            return {'id': ref.id, 'key': ref[self._key_attribute], 'time': ref.modified * 1000}
        else:
            return Sync.map_item(self, ref)

    def sync_map(self, last=None):
        
        self._items = {}
        for task in self._client.get_tasks():
            if self._check_filter(task):
                self._add_item(task.id, self.map_item(task))
        return {'items': self.items}

    def changed(self, sync):
        return Sync.changed(self, sync)

    def get(self):
        todo = self._client.get_task(self.key)
        return todo

    def delete(self):
        self._client.delete_task(self.key)
        Sync.delete(self)

    def create(self, other):
        that = other.get()
        self.logger.info(u'%s: Creating task [%s] from %s' % (self.class_name, utf8(that.title), other.class_name))
        todo = ToodledoTask(title=that.title, tdapi=self._client).create()
        return self.update(other, that, todo)
