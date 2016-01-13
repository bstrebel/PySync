#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, time, json, re, requests, logging
from pyutils import LogAdapter, strflocal, get_logger

from pysync import Sync
from enapi import *


class EnClientSync(Sync):

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

    def _check_filter(self, item):
        return True

    def sync_map(self):
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
                item = {'id': nmd.guid, 'time': nmd.updated, 'key': key, 'extra': 'EXTRA'}
                self._add_item(nmd.guid, item)

        return {'items': self.items, 'name': self.name, 'id': self.guid}

    def map_item(self, ref=None):
        if isinstance(ref, EnNote):
            #key = eval('ref.' + self._key_attribute)
            key = ref[self._key_attribute].decode('utf-8')
            return {'id': ref.guid, 'key': key, 'time': ref.updated, 'extra': 'EXTRA'}

        key = ref if ref is not None else self._key
        item = self._items.get(key)
        if item:
            return {'id': item['id'], 'key': item['key'], 'time': item['time'], 'extra': 'EXTRA'}
        else:
            return None

    def changed(self, sync):
        return Sync.changed(self, sync)

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

    def update(self, that,  note=None):
        """
        Update Evernote from other module
        :param that:    OtherClassSync (if called from sync)
                        OtherClassObject (if called from create)
        :param note:    None (if called from sync)
                        or just created EnNote
        :return:        current timestamp of updated EnNote
        """
        from oxsync import OxTaskSync
        from oxapi import OxTask
        from enapi import ENMLOfPlainText

        other = that; update = False
        if note is None:
            update = True
            note = self.get().load()
            self.logger.info('%s: Updating note [%s] from %s' % (self.class_name, note.title.decode('utf-8'),
                                                                 that.class_name))

        # check sync module type
        if isinstance(that, OxTaskSync):
            other = that.get()

        # check sync object type
        if isinstance(other, OxTask):
            # create/update note from OxTask
            task = other
            note.title = task.title

            # set evernote content for new or empty notes
            if not update:
                self.logger.info('%s: Updating note content' % (self.class_name))
                note.content = ENMLOfPlainText(OxTaskSync.enlink_remove(task.note))
                if self.options.get('ox_sourceURL', True):
                    if note.attributes.sourceURL is None:
                        note.attributes.sourceURL = task.get_url()
                if self.options.get('ox_sourceApplication'):
                    if note.attributes.sourceApplication is None:
                        note.attributes.sourceApplication = self.options.get('ox_sourceApplication', 'OxPySync')
                if self.options.get('ox_author'):
                    note.attributes.author = self.options.get('ox_author')
            else:
                preserve = None
                if note.resources:
                    preserve = "resources"
                else:
                    if note.attributes.sourceURL:
                        if not re.search(task.ox.server, note.attributes.sourceURL, re.IGNORECASE):
                            preserve = "source URL"
                    else:
                        if re.sub('\s', '', PlainTextOfENML(note.content), re.MULTILINE):
                            preserve = "content"
                if preserve:
                    self.logger.info('%s: Found %s - preserving existing note content' % (self.class_name, preserve))
                else:
                    note.content = ENMLOfPlainText(OxTaskSync.enlink_remove(task.note))
                    self.logger.info('%s: Updating note content' % (self.class_name))

            # always update reminderTime
            attribute = self.options.get('ox_reminderTime','end_time')
            if task._data.get(attribute):
                note.attributes.reminderTime = task._data.get(attribute)
                reminderTime = strflocal(task._data.get(attribute))
            else:
                note.attributes.reminderTime = None
                note.attributes.reminderOrder = None
                reminderTime = 'None'
            self.logger.info('%s: Updating note reminderTime from %s [%s]' % (self.class_name, attribute, reminderTime))

            # update note reminder status from task status
            if OxTask.get_status(task.status) == 'Done':

                if task._data.get('date_completed') is None:
                    local = time.time()
                    completed = long(local * 1000)
                else:
                    completed = task.date_completed

                note.attributes.reminderDoneTime = completed
                note.attributes.reminderTime = None
                note.attributes.reminderOrder = None

                self.logger.info('%s: Updating reminder status from done task [%s]' %
                                 (self.class_name, strflocal(completed)))

            # process categories and tags
            if task.categories:
                self.logger.info('%s: Updating tags from categories %s' % (self.class_name, task.categories))
                note.tagGuids = []
                note.tagNames = task.tagNames
            else:
                self.logger.info('%s: Removing tags from note' % (self.class_name))
                note.tagGuids = []
                note.tagNames = []

            if self.options.get('ox_status_tag'):
                if task.status:
                    tag = self.options['ox_status_tag'] + OxTask.get_status(int(task.status))
                    self.logger.info('%s: Add status tag %s to note' % (self.class_name, tag))
                    note.tagNames.append(tag)
                
            if self.options.get('ox_priority_tag'):
                if task.priority:
                    tag = self.options['ox_priority_tag'] + OxTask.get_priority(int(task.priority))
                    self.logger.info('%s: Add priority tag %s to note' % (self.class_name, tag))
                    note.tagNames.append(tag)

            if self.options.get('ox_private_tag'):
                private_tag = self.options['ox_private_tag']
                note_private_tag = False
                if private_tag in note.tagNames:
                    note_private_tag = True
                    note.tagNames.remove(private_tag)
                if task.private_flag:
                    note.tagNames.append(private_tag)
                    if not note_private_tag:
                        self.logger.info('%s: Add private tag %s to note' % (self.class_name, private_tag))
                else:
                    if note_private_tag:
                        self.logger.info('%s: Remove private tag %s from note' % (self.class_name, private_tag))
        else:
            # invalid sync object
            return None

        # perform the update
        note = self._book.update_note(note)
        self.logger.info('%s: Updating completed with timestamp %s' % (self.class_name, strflocal(note.updated)))
        return self.map_item(note)