#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, json, re, requests, logging
from pyutils import LogAdapter, strflocal, get_logger, utf8

from pysync import Sync, SyncSessionError, SyncInitError, SyncError
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

        error = u'Missing credentials in Evernote options!'
        LogAdapter(_logger, {'package': 'ensync'}).error(error)
        raise SyncSessionError(error)
        return None

    def __init__(self, client, options, logger=None):

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
            if self._book is not None:
                signature = {'label': options.get('label')}
                signature['notebook'] = self._book.name
                signature['guid'] = self._book.guid
                self.options.update({'signature': signature})
            else:
                error = u'Evernote notebook [%s] not found' % (options.get('notebook'))
                self.logger.error(error)
                raise SyncInitError(error)
        else:
            self._book = self._client.notebook(self.signature.get('guid'))
            if self._book is None:
                error = u'Evernote notebook [%s] not loaded' % (options.get(self.signature.get('guid')))
                self.logger.error(error)
                raise SyncInitError(error)

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

    @classmethod
    def add_evernote_link(self, content, link, tag='EVERNOTE', title=None):
        if content is None: content = ''
        if title:
            html = '<a href="%s">%s</a>' % (link, title)
        else:
            html = '%s' % (link)
        content += '%s: %s\n' % (tag, html)
        return content

    @classmethod
    def remove_evernote_link(self, content, tag='EVERNOTE'):
        content = content + '\n'
        if content:
            pattern = '\n%s:.*https://www.evernote.com/.*\n' % (tag)
            return re.sub(pattern, '', content, re.MULTILINE)
        else:
            return ''

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
            self.logger.debug(u'%s: Checking extra attributes %s' % (self.class_name, item_extra))

            if sync_extra is not None and item_extra is not None:
                if sync_extra.get('reminderTime') == item_extra.get('reminderTime'):
                    if sync_extra.get('reminderDoneTime') == item_extra.get('reminderDoneTime'):
                        if EnClientSync.compare_tags(sync_extra.get('tags'), item_extra.get('tags')):
                            return False
                        else:
                            self.logger.debug(u'%s: Tags changed' % (self.class_name))
                    else:
                        self.logger.debug(u'%s: Reminder done time changed' % (self.class_name))
                else:
                    self.logger.debug(u'%s: Reminder time changed' % (self.class_name))
        return True

    def get(self):
        # note = self._client.note_store.getNote(guid, True, True, True, True)
        # nmd = self._client.get_note(self._key, self._name)
        try:
            nmd = self._book.get_note(self.key)
        except Exception as e:
            self.logger.exception(u'Note [%s] not found!' % (self.title))
            return None
        return nmd

    def delete(self, sid=None):
        try:
            self._client.delete_note(self.key)
        except Exception as e:
            self.logger.exception(u'Note [%s] not found!' % (self.title))
            return None
        if sid is not None:
            self._deleted[sid] = self._items[self.key]
        Sync.delete(self, sid)

    def create(self, other, sid=None):
        that = other.get()
        if that:
            note = EnNote(title=that.title)
            self.logger.debug(u'%s: Creating note [%s] from %s' % (self.class_name, that.title, other.class_name))
            try:
                note = self._book.create_note(note)
            except Exception as e:
                self.logger.exception(u'Error creating note [%s]!' % (utf8(note.title)))
                return None

            if sid is not None:
                self._created[sid] = note
            return self.update(other, that, note, sid=sid)
        return None
