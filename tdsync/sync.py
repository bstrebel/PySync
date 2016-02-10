#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, json, re, requests, logging
from pyutils import LogAdapter, strflocal, get_logger, utf8, string

from pysync import Sync, SyncError, SyncSessionError, SyncInitError
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
            if options.get('cache') is not None:
                if options.get('secrets'):
                    secrets = options['secrets']
                    if secrets.get('client_id'):
                        if secrets.get('client_secret'):
                            return ToodledoAPI.get_session(cache=options.get('cache'),
                                                           client_id=secrets['client_id'],
                                                           client_secret=secrets['client_secret'],
                                                           logger=_logger)
                else:
                    error = 'Missing secrets in Toodledo options'
            else:
                error = 'Missing cache specification in Toodledo options'
        else:
            error = 'Missing Toodledo options'

        LogAdapter(_logger, {'package': 'tdsync'}).error(error)
        raise SyncSessionError(error)
        return None

    def __init__(self, client, options, logger=None):

        self._key_attribute = options.get('key','title')
        self._folder = None

        # self._maxsize = None

        if isinstance(client, ToodledoAPI):
            self._client = client
        else:
            self._client = ToodledoAPI.get_session(**client)

        Sync.__init__(self, options, logger, 'tdsync')

        if self.signature is None:
            if options.get('folder'):
                folder = options.get('folder')
                if self._client.folders.get(folder):
                    self._folder = self._client.folders[folder]
                    signature = {'label': options.get('label'),
                                 'folder': self._folder['name'],
                                 'id': self._folder['id']}
                    self.options.update({'signature': signature})
                else:
                    error = u'Folder [%s] not found!' % (utf8(folder))
                    self.logger.error(error)
                    raise SyncInitError(error)
            else:
                self.logger.warning(u'No folder specified in sync options')
        else:
            self._folder = self.client.folders[self.signature['id']]

    # @property
    # def maxsize(self): return self._maxsize
    #
    # @maxsize.setter
    # def maxsize(self, value): self._maxsize = value

    @property
    def folder(self): return self._folder

    @property
    def client(self): return self._client

    @property
    def need_last_map(self): return True

    # def _check_filter(self, item):
    #     return True

    def map_item(self, ref=None):
        if isinstance(ref, ToodledoTask):
            # return {'id': ref.id, 'key': ref[self._key_attribute], 'time': ref.modified * 1000}
            return {'id': ref._id, 'key': ref[self._key_attribute], 'time': ref._time}
        else:
            return Sync.map_item(self, ref)

    def sync_map(self, last=None):

        self._items = {}

        for task in self._client.get_tasks(self.folder.id):
            if self._check_filter(task):
                self._add_item(task._id, self.map_item(task))

        return {'items': self.items}

    def changed(self, sync):
        return Sync.changed(self, sync)

    def get(self):
        todo = self._client.get_task(self.key)
        return todo

    def delete(self, sid=None):
        self._client.delete_task(self.key)
        Sync.delete(self, sid)

    def create(self, other, sid=None):
        that = other.get()
        if that:
            self.logger.debug(u'%s: Creating task [%s] from %s' % (self.class_name, utf8(that.title), other.class_name))
            todo = self._client.create_task(title=that.title, folder=self.folder.id)
            return self.update(other, that, todo, sid=sid)
        return None

    @classmethod
    def end_session(cls, logger, **kwargs):
        logger.debug(u'End session called for %s' % (cls))
        # invalidate current session and clear caches
        ToodledoAPI.set_session(None)

    def commit_sync(self, lr, opts, logger):

        # update server from cache
        self._client.end_session()

        # check for committed changes after API calls
        # _deleted => items, that are really deleted on server
        # _created => items, that are really created and mapped to new ids

        if self._client.tasks:
            if self._client.tasks._created:
                # replace uuid from created tasks with toodledo server id
                created = self._client.tasks._created
                for sid in opts['sync']['map']:
                    item = opts['sync']['map'][sid][lr]
                    uuid = item['id']
                    if isinstance(uuid, str):
                        if uuid in created:
                            item['id'] = created[uuid]['id']
                            item['time'] = created[uuid]['modified'] * 1000
                        else:
                            # create failed, remove from sync_map during check
                            opts['sync']['map'][sid][lr] = None

                self._client.tasks._created = {}
        return opts
