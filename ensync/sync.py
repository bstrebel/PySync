#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, json, re, requests, logging
from pyutils import LogAdapter, strflocal, get_logger

from pysync import Sync
from enapi import *


class EnClientSync(Sync):

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
            if options.get('secrets'):
                if options['secrets'].get('token'):
                    return EnClient.get_client(token=options['secrets']['token'],
                                               logger=_logger)

        LogAdapter(_logger, {'package': 'ensync'}).error('Missing credentials in Evernote options!')
        return None

    def __init__(self, client, options, logger=None):

        #self._name = options.get('notebook')
        #self._guid = options.get('guid')
        self._key_attribute = options.get('key','title')
        self._book = None
        self._maxsize = None

        if isinstance(client, EnClient):
            self._client = client
        else:
            self._client = EnClient.get_client(**client)

        Sync.__init__(self, options, logger, 'ensync')

        if options.get('signature') is None:
            self._book = self._client.notebook(options.get('notebook'))
            signature = {'label': options.get('label')}
            signature['notebook'] = self._book.name
            signature['guid'] = self._book.guid
            self.options.update({'signature': signature})

    def __repr__(self): return self.label
    # return 'EnClient:%s' % (self._name)

    def __str__(self): return self.label
    # return 'EnClient:%s' % (self._name)

    @property
    def class_name(self): return self.label
    # return 'EnClient:%s' % (self._name)

    @property
    def maxsize(self): return self._maxsize

    @maxsize.setter
    def maxsize(self, value): self._maxsize = value

    @property
    def client(self): return self._client

    @property
    def guid(self): return self.signature.get('guid')

    @property
    def name(self): return self.signature.get('notebook')

    @property
    def need_last_map(self): return False

    def _check_filter(self, item):
        return True

    def sync_map(self, last=None):
        # from enapi import EnBook
        if self.guid:
            self._book = EnBook.initialize(self._client.note_store.getNotebook(self.guid))
            #self._name = self._book.name
        else:
            self._book = self._client.notebook(self._name)
            #self._guid = self._book.guid

        self._items = {}
        for key in self._book:
            nmd = self._book.get_note(key)
            #key = eval('nmd.' + self._key_attribute)
            key = nmd[self._key_attribute].decode('utf-8')
            if self._check_filter(nmd):
                item = {'id': nmd.guid, 'time': nmd.updated, 'key': key, 'extra': EnClientSync.extra(nmd)}
                self._add_item(nmd.guid, item)

        return {'items': self.items, 'name': self.name, 'id': self.guid}

    def map_item(self, ref=None):
        if isinstance(ref, EnNote):
            #key = eval('ref.' + self._key_attribute)
            key = ref[self._key_attribute].decode('utf-8')
            return {'id': ref.guid, 'key': key, 'time': ref.updated, 'extra': EnClientSync.extra(ref)}

        key = ref if ref is not None else self._key
        item = self._items.get(key)
        if item:
            return {'id': item['id'], 'key': item['key'], 'time': item['time'], 'extra': item.get('extra')}
        else:
            return None

    def changed(self, sync):

        if not Sync.changed(self, sync):

            # check extra attributes
            sync_extra = sync.get('extra')

            item = self._items.get(self._key)
            item_extra = item.get('extra')
            self.logger.debug('%s: Checking extra attributes %s' % (self.class_name, item_extra))

            if sync_extra is not None and item_extra is not None:
                if sync_extra.get('reminderTime') == item_extra.get('reminderTime'):
                    if sync_extra.get('reminderDoneTime') == item_extra.get('reminderDoneTime'):
                        if EnClientSync.compare_tags(sync_extra.get('tags'), item_extra.get('tags')):
                            return False
                        else:
                            self.logger.info('%s: Tags changed' % (self.class_name))
                    else:
                        self.logger.info('%s: Reminder done time changed' % (self.class_name))
                else:
                    self.logger.info('%s: Reminder time changed' % (self.class_name))
        return True

    def get(self):
        #note = self._client.note_store.getNote(guid, True, True, True, True)
        #nmd = self._client.get_note(self._key, self._name)
        nmd = self._book.get_note(self.key)
        return nmd

    def delete(self):
        self._client.delete_note(self.key)
        Sync.delete(self)

    def create(self, that):
        other = that.get()
        note = EnNote(title=other.title)
        self.logger.info('%s: Creating note [%s] from %s' % (self.class_name, other.title, other.__class__.__name__))
        note = self._book.create_note(note)
        return self.update(other, note)
