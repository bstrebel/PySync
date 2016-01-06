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

        if logger is None:
            self._logger = get_logger('ensync', logging.DEBUG)
        else:
            self._logger = logger

        self._adapter = LogAdapter(self._logger, {'package': 'ensync'})

        self._options = options
        self._name = options.get('notebook')
        self._guid = options.get('guid')
        self._key_attribute = options.get('key')
        self._book = None
        self._maxsize = None

        if isinstance(client, EnClient):
            self._client = client
        else:
            self._client = EnClient.get_client(**client)

        Sync.__init__(self, self._logger)

    def __repr__(self):
        return 'EnClient:%s' % (self._name)

    def __str__(self):
        return 'EnClient:%s' % (self._name)

    @property
    def class_name(self): return 'EnClient:%s' % (self._name)

    @property
    def maxsize(self): return self._maxsize

    @maxsize.setter
    def maxsize(self, value): self._maxsize = value

    @property
    def logger(self): return self._adapter

    @property
    def client(self): return self._client

    @property
    def guid(self): return self._guid

    @property
    def name(self): return self._name

    def sync_map(self):
        # from enapi import EnBook
        if self.guid:
            self._book = EnBook.initialize(self._client.note_store.getNotebook(self.guid))
            self._name = self._book.name
        else:
            self._book = self._client.notebook(self._name)
            self._guid = self._book.guid

        self._items = {}
        for key in self._book:
            nmd = self._book.get_note(key)
            self._add_item(nmd.guid, nmd.updated, eval('nmd.' + self._key_attribute))
        return {'items': self.items, 'name': self.name, 'id': self.guid}

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
        updated = self.update(other, note)
        return note.guid, updated, note.title.decode('utf-8')

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
                if note.attributes.sourceURL is None:
                    note.attributes.sourceURL = task.get_url()
                if note.attributes.sourceApplication is None:
                    note.attributes.sourceApplication = 'OxPySync'
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

            if task.end_date:
                note.attributes.reminderTime = task.end_date
                self.logger.info('%s: Updating reminder time from due date (%s)' % (self.class_name, strflocal(task.end_date)))

            if OxTask.get_status(task.status) == 'done':
                local = time.time()
                note.attributes.reminderDoneTime = long(local * 1000)
                note.attributes.reminderTime = 0L
                self.logger.info('%s: Updating reminder done time from localtime (%s)' % (self.class_name, strflocal(local)))

            if task.categories:
                self.logger.info('%s: Updating tags from categories %s' % (self.class_name, task.categories))
                note.tagGuids = []
                note.tagNames = task.tag_names('ascii')

        else:
            # invalid sync object
            return None

        # perform the update
        note = self._book.update_note(note)
        self.logger.info('%s: Updating completed with timestamp %s' % (self.class_name, strflocal(note.updated)))
        return note.updated
